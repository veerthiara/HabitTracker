"""Tests for HabitTracker SQL Catalog Adapter.

Verifies the catalog against actual SQLAlchemy ORM metadata.
"""

import pytest
from habittracker.domain.sql_catalog import (
    HabitTrackerSqlCatalogProvider,
    build_habittracker_catalog,
    get_habittracker_catalog,
)
from habittracker.sql_analytics.contracts import SqlSchemaCatalog


# ── Type mapping (exact, no fallbacks) ────────────────────────────────────────

CATALOG_TO_SQLALCHEMY_TYPES = {
    "uuid": {"uuid"},
    "varchar": {"varchar", "character varying"},
    "text": {"text"},
    "integer": {"integer", "int4"},
    "boolean": {"boolean", "bool"},
    "timestamp with time zone": {"timestamp with time zone", "timestamptz", "datetime"},
    "date": {"date"},
    "vector": {"vector"},
}


def sqlalchemy_type_matches(catalog_type: str, orm_type) -> bool:
    """Check if catalog type string matches SQLAlchemy type.

    Raises AssertionError for unknown catalog types instead of silently passing.
    """
    orm_str = str(orm_type).lower()
    cat_lower = catalog_type.lower()

    # Find matching key in our known mappings
    matched_key = None
    for key in CATALOG_TO_SQLALCHEMY_TYPES:
        if key in cat_lower:
            matched_key = key
            break

    if matched_key is None:
        raise AssertionError(
            f"Unknown catalog data_type '{catalog_type}' — add to CATALOG_TO_SQLALCHEMY_TYPES"
        )

    return any(v in orm_str for v in CATALOG_TO_SQLALCHEMY_TYPES[matched_key])


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestHabitTrackerCatalogProvider:
    def test_implements_provider_interface(self):
        provider = HabitTrackerSqlCatalogProvider()
        assert hasattr(provider, "get_catalog")
        catalog = provider.get_catalog()
        assert isinstance(catalog, SqlSchemaCatalog)

    def test_catalog_name_and_version(self):
        catalog = get_habittracker_catalog()
        assert catalog.catalog_name == "habittracker"
        assert catalog.catalog_version == "1.0"
        assert catalog.dialect == "postgresql"


class TestCatalogAgainstORM:
    """Compare catalog definitions against actual SQLAlchemy ORM models.

    Rule: Every table/column exposed by the approved catalog must exist in the ORM.
    The catalog may expose a safe subset of ORM tables/columns.
    """

    @pytest.fixture
    def catalog(self):
        return get_habittracker_catalog()

    @pytest.fixture
    def orm_models(self):
        from habittracker.models.orm.habittracker import (
            User,
            Habit,
            HabitLog,
            BottleEvent,
            DailySummary,
            Note,
        )
        return {
            "users": User,
            "habits": Habit,
            "habit_logs": HabitLog,
            "bottle_events": BottleEvent,
            "daily_summaries": DailySummary,
            "notes": Note,
        }

    def test_all_catalog_tables_exist_in_orm(self, catalog, orm_models):
        """Every table in the approved catalog must have a corresponding ORM model."""
        orm_table_names = set(orm_models.keys())
        catalog_table_names = {t.name for t in catalog.tables}
        missing = catalog_table_names - orm_table_names
        assert not missing, f"Catalog tables missing from ORM: {missing}"

    def test_all_catalog_columns_validated(self, catalog, orm_models):
        """For every catalog table, validate all its columns against ORM metadata."""
        for table in catalog.tables:
            orm_table = orm_models[table.name].__table__
            orm_cols = {c.name: c for c in orm_table.columns}

            for col in table.columns:
                # Column must exist in ORM
                assert col.name in orm_cols, \
                    f"{table.name}.{col.name}: catalog column not found in ORM"

                orm_col = orm_cols[col.name]

                # Primary key flag must match
                orm_is_pk = col.name in orm_table.primary_key.columns
                assert col.is_primary_key == orm_is_pk, \
                    f"{table.name}.{col.name}: is_primary_key={col.is_primary_key} but ORM says {orm_is_pk}"

                # Nullable flag must match
                assert col.nullable == orm_col.nullable, \
                    f"{table.name}.{col.name}: nullable={col.nullable} but ORM says {orm_col.nullable}"

                # Foreign key flag must match
                orm_has_fk = len(orm_col.foreign_keys) > 0
                assert col.is_foreign_key == orm_has_fk, \
                    f"{table.name}.{col.name}: is_foreign_key={col.is_foreign_key} but ORM has FK={orm_has_fk}"

                # If foreign key, target must match
                if col.is_foreign_key and col.foreign_key_target:
                    orm_fk_targets = {
                        f"{fk.column.table.name}.{fk.column.name}"
                        for fk in orm_col.foreign_keys
                    }
                    assert col.foreign_key_target in orm_fk_targets, \
                        f"{table.name}.{col.name}: foreign_key_target={col.foreign_key_target} not in ORM targets {orm_fk_targets}"

                # Data type must be compatible (strict, no fallback)
                assert sqlalchemy_type_matches(col.data_type, orm_col.type), \
                    f"{table.name}.{col.name}: catalog type '{col.data_type}' incompatible with ORM type '{orm_col.type}'"

    def test_primary_keys_match(self, catalog, orm_models):
        for table in catalog.tables:
            orm_table = orm_models[table.name].__table__
            orm_pks = {c.name for c in orm_table.primary_key.columns}
            catalog_pks = set(table.primary_keys)
            assert catalog_pks == orm_pks, f"PK mismatch for {table.name}: catalog={catalog_pks}, orm={orm_pks}"

    def test_foreign_keys_represented(self, catalog, orm_models):
        """Every ORM FK should have a corresponding catalog column with is_foreign_key=True."""
        for table in catalog.tables:
            orm_table = orm_models[table.name].__table__
            orm_fks = set()
            for fk in orm_table.foreign_keys:
                orm_fks.add(fk.parent.name)
            catalog_fks = {c.name for c in table.columns if c.is_foreign_key}
            assert orm_fks.issubset(catalog_fks), \
                f"Missing FK columns in catalog for {table.name}: {orm_fks - catalog_fks}"

    def test_embedding_column_excluded(self, catalog):
        """Embedding column is excluded entirely from approved catalog per policy."""
        notes_table = catalog.get_table("notes")
        embedding_col = notes_table.get_column("embedding")
        assert embedding_col is None
        selectable_names = {c.name for c in notes_table.selectable_columns()}
        assert "embedding" not in selectable_names

    def test_relationships_match_orm_fks(self, catalog, orm_models):
        """Catalog relationships should correspond to actual FKs."""
        for rel in catalog.relationships:
            left_table = catalog.get_table(rel.left_table)
            right_table = catalog.get_table(rel.right_table)
            orm_left = orm_models[rel.left_table].__table__
            fk_found = False
            for fk in orm_left.foreign_keys:
                if fk.parent.name == rel.left_column:
                    target_table = fk.column.table.name
                    target_col = fk.column.name
                    if target_table == rel.right_table and target_col == rel.right_column:
                        fk_found = True
                        break
            assert fk_found, f"ORM FK not found for {rel.left_table}.{rel.left_column} -> {rel.right_table}.{rel.right_column}"


class TestCatalogStructure:
    def test_six_tables_present(self):
        catalog = get_habittracker_catalog()
        names = {t.name for t in catalog.tables}
        expected = {"users", "habits", "habit_logs", "bottle_events", "daily_summaries", "notes"}
        assert names == expected

    def test_all_tables_have_descriptions(self):
        catalog = get_habittracker_catalog()
        for table in catalog.tables:
            assert table.description and len(table.description) > 10

    def test_all_columns_have_descriptions(self):
        catalog = get_habittracker_catalog()
        for table in catalog.tables:
            for col in table.columns:
                assert col.description and len(col.description) > 5

    def test_user_scoped_tables_have_user_scope_column(self):
        catalog = get_habittracker_catalog()
        for table in catalog.tables:
            if table.user_scoped and table.scope_strategy == "direct":
                scope_cols = table.user_scope_columns()
                assert len(scope_cols) > 0, f"{table.name} is user_scoped but has no is_user_scope columns"

    def test_users_table_not_user_scoped(self):
        catalog = get_habittracker_catalog()
        users = catalog.get_table("users")
        assert users.user_scoped is False

    def test_all_other_tables_user_scoped(self):
        catalog = get_habittracker_catalog()
        for table in catalog.tables:
            if table.name != "users":
                assert table.user_scoped is True, f"{table.name} should be user_scoped"

    def test_global_rules_present(self):
        catalog = get_habittracker_catalog()
        assert len(catalog.global_rules) > 5
        rules_text = " ".join(catalog.global_rules)
        assert "SELECT" in rules_text
        assert "user_id" in rules_text
        assert "LIMIT" in rules_text
        assert "CTE" in rules_text or "WITH" in rules_text

    def test_embedding_excluded_from_select(self):
        catalog = get_habittracker_catalog()
        notes = catalog.get_table("notes")
        selectable = notes.selectable_columns()
        selectable_names = {c.name for c in selectable}
        assert "embedding" not in selectable_names