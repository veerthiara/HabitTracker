"""SQL schema service.

Derives the SQL analytics schema from the existing SQLAlchemy ORM models
instead of duplicating table/column definitions.

The ORM models under habittracker/models/orm/ are the single source of
truth for table structure (column names, types, foreign keys).  This
service reads them via SQLAlchemy's table introspection API and assembles
a SchemaContext from them.

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
  - ALLOWED_TABLES set

Result: adding a column to an ORM model makes it appear in the SQL
analytics schema automatically.  Removing a column removes it.  The only
manual step is optionally adding a business description for new columns.
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


# ── SQLAlchemy type → prompt string ───────────────────────────────────────────


def _col_type_str(col) -> str:  # noqa: ANN001
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


# ── Per-table configuration ────────────────────────────────────────────────────
# Everything here is what the ORM cannot tell us:
#   description  — table-level sentence for the LLM prompt
#   column_descriptions — business context for specific columns
#   exclude       — columns to hide from the LLM (embeddings, internal fields)
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
        # Exclude ML/internal columns — not useful for SQL analytics
        "exclude": {"embedding", "source"},
    },
}

_SAFETY_CONSTRAINTS: list[str] = [
    "Always filter by user_id using the provided :user_id parameter.",
    "Never query tables not listed above.",
    "Only SELECT statements are permitted.",
    "Keep result sets small: add LIMIT unless the question explicitly asks for all data.",
]


# ── Builders (derive structure from ORM) ──────────────────────────────────────


def _build_table_def(orm_class: type, config: dict) -> TableDef:
    exclude: set[str] = config.get("exclude", set())
    col_descriptions: dict[str, str] = config.get("column_descriptions", {})
    columns = [
        ColumnDef(
            name=col.name,
            type=_col_type_str(col),
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


def _build_foreign_keys(approved_tables: frozenset[str]) -> list[ForeignKeyDef]:
    """Walk ORM columns and collect FK relationships between approved tables."""
    fks: list[ForeignKeyDef] = []
    for orm_class in _TABLE_CONFIG:
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


def _build_schema() -> SchemaContext:
    tables = [_build_table_def(orm_cls, cfg) for orm_cls, cfg in _TABLE_CONFIG.items()]
    approved = frozenset(t.name for t in tables)
    return SchemaContext(
        tables=tables,
        foreign_keys=_build_foreign_keys(approved),
        constraints=_SAFETY_CONSTRAINTS,
    )


# ── Module-level instances ─────────────────────────────────────────────────────

SCHEMA: SchemaContext = _build_schema()
ALLOWED_TABLES: frozenset[str] = SCHEMA.allowed_tables


# ── Public API ────────────────────────────────────────────────────────────────


def get_schema_summary() -> str:
    """Return the LLM-ready schema prompt string derived from the ORM models."""
    return SCHEMA.to_prompt_string()


def is_table_allowed(table_name: str) -> bool:
    """Return True if the table name is in the approved list."""
    return SCHEMA.is_table_allowed(table_name)
