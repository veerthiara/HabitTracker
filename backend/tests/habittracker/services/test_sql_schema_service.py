"""Tests for habittracker.services.sql_schema_service.

Guards the _TABLE_CONFIG dictionary against three classes of mistake that
would silently produce an incorrect LLM schema prompt:

  1. An ORM class listed in _TABLE_CONFIG that no longer exists (or was
     renamed) in the ORM models directory.

  2. A column name listed in `column_descriptions` that does not exist in
     the corresponding ORM table — the LLM would receive a description
     for a phantom column.

  3. A column name listed in `exclude` that does not exist in the
     corresponding ORM table — we'd claim to hide a column that isn't
     there, masking a refactor/rename.

  4. A column that exists in the ORM **and is not excluded** must appear
     in the rendered SCHEMA — so the LLM sees a complete, accurate picture
     of what it can query.
"""

import pytest

from habittracker.services.sql_schema_service import (
    SCHEMA,
    _TABLE_CONFIG,  # noqa: PLC2701 — deliberate white-box test
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _orm_columns(orm_class: type) -> set[str]:
    """Return the set of column names defined on an ORM model."""
    return {col.name for col in orm_class.__table__.columns}


def _schema_columns(tablename: str) -> set[str]:
    """Return the column names present in the rendered SchemaContext."""
    for table in SCHEMA.tables:
        if table.name == tablename:
            return {col.name for col in table.columns}
    return set()


# ── Test 1: every ORM class in _TABLE_CONFIG has a real __table__ ─────────────


class TestTableConfigOrmClassesExist:
    """Each key in _TABLE_CONFIG must be a SQLAlchemy ORM model with a table."""

    @pytest.mark.parametrize("orm_class", list(_TABLE_CONFIG.keys()))
    def test_orm_class_has_table_attribute(self, orm_class: type) -> None:
        assert hasattr(orm_class, "__table__"), (
            f"{orm_class.__name__} has no __table__ — is it a real ORM model?"
        )

    @pytest.mark.parametrize("orm_class", list(_TABLE_CONFIG.keys()))
    def test_orm_class_has_tablename_attribute(self, orm_class: type) -> None:
        assert hasattr(orm_class, "__tablename__"), (
            f"{orm_class.__name__} has no __tablename__"
        )

    @pytest.mark.parametrize("orm_class", list(_TABLE_CONFIG.keys()))
    def test_orm_class_table_has_columns(self, orm_class: type) -> None:
        assert len(list(orm_class.__table__.columns)) > 0, (
            f"{orm_class.__name__}.__table__ has no columns"
        )


# ── Test 2: column_descriptions only reference real columns ──────────────────


class TestColumnDescriptionsMatchOrm:
    """Every key in column_descriptions must be a real column in that ORM table."""

    @pytest.mark.parametrize("orm_class,config", list(_TABLE_CONFIG.items()))
    def test_column_descriptions_are_real_columns(
        self, orm_class: type, config: dict
    ) -> None:
        real = _orm_columns(orm_class)
        described = set(config.get("column_descriptions", {}).keys())
        phantom = described - real
        assert not phantom, (
            f"{orm_class.__name__}: column_descriptions references columns not "
            f"in the ORM table: {phantom!r}. Real columns: {real!r}"
        )


# ── Test 3: exclude only references real columns ──────────────────────────────


class TestExcludeMatchesOrm:
    """Every name in the exclude set must be a real column in that ORM table."""

    @pytest.mark.parametrize("orm_class,config", list(_TABLE_CONFIG.items()))
    def test_excluded_columns_are_real(
        self, orm_class: type, config: dict
    ) -> None:
        real = _orm_columns(orm_class)
        excluded = config.get("exclude", set())
        phantom = excluded - real
        assert not phantom, (
            f"{orm_class.__name__}: exclude references columns not in the ORM "
            f"table: {phantom!r}. Real columns: {real!r}"
        )


# ── Test 4: every non-excluded ORM column appears in the rendered SCHEMA ──────


class TestSchemaCoversAllColumns:
    """The rendered SCHEMA must contain every column that is not excluded.

    This ensures the LLM prompt is complete — no column silently dropped.
    """

    @pytest.mark.parametrize("orm_class,config", list(_TABLE_CONFIG.items()))
    def test_all_non_excluded_columns_in_schema(
        self, orm_class: type, config: dict
    ) -> None:
        real = _orm_columns(orm_class)
        excluded = config.get("exclude", set())
        expected = real - excluded
        in_schema = _schema_columns(orm_class.__tablename__)
        missing = expected - in_schema
        assert not missing, (
            f"{orm_class.__tablename__}: these ORM columns are neither excluded "
            f"nor present in the schema: {missing!r}"
        )
