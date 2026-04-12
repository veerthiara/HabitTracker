"""SQL schema service — SqlSchemaService.

SqlSchemaService derives the approved analytics schema from the existing
SQLAlchemy ORM models instead of duplicating table/column definitions.

Design:
  - All ORM introspection helpers (_col_type_str, _build_table_def,
    _build_foreign_keys, _build_schema) are private static methods of the
    class, keeping all SQL schema logic encapsulated in one place.
  - The _TABLE_CONFIG dict and _SAFETY_CONSTRAINTS list are module-level
    configuration data (not business logic), and are passed into the build
    helpers so they can be replaced in tests if needed.
  - sql_schema_service is the module-level singleton consumed by callers.
    Callers import the instance, not the class.

What this service owns (not derivable from ORM):
  - Which tables are approved for SQL analytics (_TABLE_CONFIG keys)
  - Per-column business-friendly descriptions (for LLM prompt quality)
  - Per-table descriptions
  - Which columns to exclude from the LLM schema (e.g. embedding vectors)
  - The safety constraints injected into every prompt

What is derived automatically from the ORM:
  - Column names and order
  - Column types (mapped to prompt-friendly strings)
  - Foreign key relationships between approved tables
  - allowed_tables set
"""

from __future__ import annotations

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from habittracker.models.orm.habittracker.bottle_event import BottleEvent
from habittracker.models.orm.habittracker.habit import Habit
from habittracker.models.orm.habittracker.habit_log import HabitLog
from habittracker.models.orm.habittracker.note import Note
from habittracker.models.orm.habittracker.user import User
from habittracker.schemas.sql_schema import (
    ColumnDef,
    ForeignKeyDef,
    SchemaContext,
    TableDef,
)


# ── Per-table configuration ────────────────────────────────────────────────────
# Everything here is what the ORM cannot tell us:
#   description         — table-level sentence for the LLM prompt
#   column_descriptions — business context for specific columns
#   exclude             — columns to hide from the LLM (embeddings, internals)
#
# To approve a new table for SQL analytics, add an entry below.

_TABLE_CONFIG: dict[type, dict] = {
    User: {
        "description": "one row per authenticated user",
        "column_descriptions": {},
        "exclude": set(),
    },
    Habit: {
        "description": "habits defined by the user",
        "column_descriptions": {
            "name":        "habit name as entered by the user",
            "description": "optional longer description",
            "frequency":   "one of: daily, weekly, custom",
            "is_active":   "false means the habit has been archived",
        },
        "exclude": set(),
    },
    HabitLog: {
        "description": "one row = one completion of a habit on a date",
        "column_descriptions": {
            "logged_date": "calendar date the habit was completed (no time component)",
            "notes":       "optional free-text note attached to this log entry",
        },
        "exclude": set(),
    },
    BottleEvent: {
        "description": "one row = one bottle/drink recorded by the user",
        "column_descriptions": {
            "event_ts":  "exact moment the bottle event was recorded",
            "volume_ml": "liquid volume in millilitres for this event",
        },
        "exclude": set(),
    },
    Note: {
        "description": "free-text journal entries written by the user",
        "column_descriptions": {
            "content": "full text of the note",
        },
        "exclude": {"embedding", "source"},
    },
}

_SAFETY_CONSTRAINTS: list[str] = [
    "Always filter by user_id using the provided :user_id parameter.",
    "Never query tables not listed above.",
    "Only SELECT statements are permitted.",
    "Keep result sets small: add LIMIT unless the question explicitly asks for all data.",
]


# ── Service class ─────────────────────────────────────────────────────────────


class SqlSchemaService:
    """Provides schema introspection and prompt rendering for SQL analytics.

    The schema is derived once from the ORM at construction time and then
    served immutably for the lifetime of the process.
    """

    def __init__(
        self,
        table_config: dict[type, dict] = _TABLE_CONFIG,
        safety_constraints: list[str] = _SAFETY_CONSTRAINTS,
    ) -> None:
        self._schema = self._build_schema(table_config, safety_constraints)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _col_type_str(col) -> str:  # noqa: ANN001
        """Map a SQLAlchemy column type to a prompt-friendly string."""
        t = col.type
        if isinstance(t, UUID):
            return "UUID"
        if isinstance(t, DateTime):
            return "TIMESTAMPTZ" if t.timezone else "TIMESTAMP"
        if isinstance(t, Date):
            return "DATE"
        if isinstance(t, Boolean):
            return "BOOL"
        if isinstance(t, Integer):
            return "INTEGER"
        if isinstance(t, (String, Text)):
            return "TEXT"
        return type(t).__name__.upper()

    @staticmethod
    def _build_table_def(orm_class: type, config: dict) -> TableDef:
        """Build a TableDef by introspecting the ORM model's __table__."""
        exclude: set[str] = config.get("exclude", set())
        col_descriptions: dict[str, str] = config.get("column_descriptions", {})
        columns = [
            ColumnDef(
                name=col.name,
                type=SqlSchemaService._col_type_str(col),
                description=col_descriptions.get(col.name, ""),
            )
            for col in orm_class.__table__.columns
            if col.name not in exclude
        ]
        return TableDef(
            name=orm_class.__tablename__,
            description=config["description"],
            columns=columns,
        )

    @staticmethod
    def _build_foreign_keys(
        table_config: dict[type, dict],
        approved_tables: frozenset[str],
    ) -> list[ForeignKeyDef]:
        """Walk ORM columns and collect FK relationships between approved tables."""
        fks: list[ForeignKeyDef] = []
        for orm_class in table_config:
            for col in orm_class.__table__.columns:
                for fk in col.foreign_keys:
                    target_table = fk.target_fullname.split(".")[0]
                    if target_table in approved_tables:
                        fks.append(
                            ForeignKeyDef(
                                from_col=f"{orm_class.__tablename__}.{col.name}",
                                to_col=fk.target_fullname,
                            )
                        )
        return fks

    @staticmethod
    def _build_schema(
        table_config: dict[type, dict],
        safety_constraints: list[str],
    ) -> SchemaContext:
        """Construct a SchemaContext from the ORM table config."""
        tables = [
            SqlSchemaService._build_table_def(orm_cls, cfg)
            for orm_cls, cfg in table_config.items()
        ]
        approved = frozenset(t.name for t in tables)
        return SchemaContext(
            tables=tables,
            foreign_keys=SqlSchemaService._build_foreign_keys(table_config, approved),
            constraints=safety_constraints,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def schema(self) -> SchemaContext:
        """The full SchemaContext derived from the ORM."""
        return self._schema

    @property
    def allowed_tables(self) -> frozenset[str]:
        """Set of table names approved for SQL analytics queries."""
        return self._schema.allowed_tables

    def get_summary(self) -> str:
        """Return the LLM-ready schema prompt string."""
        return self._schema.to_prompt_string()

    def is_table_allowed(self, table_name: str) -> bool:
        """Return True if the table name is in the approved list."""
        return self._schema.is_table_allowed(table_name)


# ── Module-level singleton ────────────────────────────────────────────────────
# Callers import this instance, not the class.

sql_schema_service = SqlSchemaService()

