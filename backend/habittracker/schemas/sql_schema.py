"""Pydantic models describing the approved database schema for SQL analytics.

These models define *what the schema is* — tables, columns, foreign keys,
and safety constraints.  They have no knowledge of prompts, LLMs, or
service logic; that belongs in sql_schema_service.py.

Following the FastAPI convention, this file is a pure schema definition.
The service layer (services/sql_schema_service.py) imports these models,
instantiates the SCHEMA object, and exposes the derived helpers used by
the rest of the SQL analytics pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel


class ColumnDef(BaseModel):
    """A single column in an approved table."""

    name: str
    type: str
    description: str


class TableDef(BaseModel):
    """An approved table and its columns."""

    name: str
    description: str
    columns: list[ColumnDef]


class ForeignKeyDef(BaseModel):
    """A foreign-key relationship between two approved tables."""

    from_col: str  # "table.column"
    to_col: str    # "table.column"


class SchemaContext(BaseModel):
    """The full schema context: tables, foreign keys, and safety constraints.

    This is the single source of truth for everything the SQL analytics
    path is allowed to know about the database.  All derived values
    (allowed table set, LLM prompt string) are computed from an instance
    of this model, not maintained separately.
    """

    tables: list[TableDef]
    foreign_keys: list[ForeignKeyDef]
    constraints: list[str]

    @property
    def allowed_tables(self) -> frozenset[str]:
        """Derive the allowed table set directly from the table list."""
        return frozenset(t.name for t in self.tables)

    def is_table_allowed(self, table_name: str) -> bool:
        return table_name.lower() in self.allowed_tables

    def to_prompt_string(self) -> str:
        """Render a compact, LLM-friendly schema description from the model."""
        lines: list[str] = [
            "Database: PostgreSQL",
            "Timezone: all timestamps are stored with timezone (timestamptz)."
            " Use DATE() or AT TIME ZONE to work with dates.",
            "",
            "Tables you MAY query (SELECT only):",
        ]
        for table in self.tables:
            lines.append("")
            lines.append(f"{table.name}  ({table.description})")
            for col in table.columns:
                lines.append(f"  {col.name:<14}{col.type:<14}{col.description}")
        lines.append("")
        lines.append("Relationships:")
        for fk in self.foreign_keys:
            lines.append(f"  {fk.from_col} → {fk.to_col}")
        lines.append("")
        lines.append("Important constraints:")
        for c in self.constraints:
            lines.append(f"  - {c}")
        return "\n".join(lines)
