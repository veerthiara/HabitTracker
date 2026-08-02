"""Generic SQL Analytics Core Contracts.

Reusable Pydantic models for column, table, relationship, and catalog definitions.
Zero dependencies on application-specific code.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Annotated


class SqlColumnDefinition(BaseModel):
    """A single column definition in the approved schema catalog.

    Validation rules enforced at model construction time.
    """

    name: Annotated[str, Field(min_length=1, description="Column name")]
    description: Annotated[str, Field(min_length=1, description="Business-friendly description")]
    data_type: Annotated[str, Field(min_length=1, description="Database type (e.g., uuid, varchar(255), timestamp with time zone)")]
    nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_target: str | None = None
    is_user_scope: bool = False
    allowed_for_select: bool = True
    sensitive: bool = False

    @model_validator(mode="after")
    def _validate_fk_and_sensitive(self) -> "SqlColumnDefinition":
        if self.is_foreign_key and not self.foreign_key_target:
            raise ValueError("foreign_key_target required when is_foreign_key=True")
        if self.sensitive and self.allowed_for_select:
            # Auto-correct: sensitive columns cannot be selectable
            object.__setattr__(self, "allowed_for_select", False)
        return self


class SqlTableDefinition(BaseModel):
    """A single table definition in the approved schema catalog."""

    name: Annotated[str, Field(min_length=1, description="Table name")]
    description: Annotated[str, Field(min_length=1, description="Business-friendly description")]
    columns: tuple[SqlColumnDefinition, ...]
    user_scoped: bool = False
    allowed_for_select: bool = True
    aliases: tuple[str, ...] = ()
    business_rules: tuple[str, ...] = ()
    scope_strategy: str = "direct"
    scope_description: str | None = None

    @property
    def primary_keys(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.is_primary_key)

    @model_validator(mode="after")
    def _validate_table(self) -> "SqlTableDefinition":
        if not self.columns:
            raise ValueError("at least one column required")
        col_names = [c.name for c in self.columns]
        if len(col_names) != len(set(col_names)):
            raise ValueError("column names must be unique")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("aliases must be unique")
        if self.user_scoped and self.scope_strategy == "direct":
            if not any(c.is_user_scope for c in self.columns):
                raise ValueError("user_scoped=True with direct strategy requires at least one is_user_scope=True column")
        return self

    def get_column(self, name: str) -> SqlColumnDefinition | None:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def selectable_columns(self) -> tuple[SqlColumnDefinition, ...]:
        return tuple(c for c in self.columns if c.allowed_for_select and not c.sensitive)

    def user_scope_columns(self) -> tuple[SqlColumnDefinition, ...]:
        return tuple(c for c in self.columns if c.is_user_scope)


class SqlRelationshipDefinition(BaseModel):
    """A foreign-key relationship between two tables."""

    left_table: Annotated[str, Field(min_length=1)]
    left_column: Annotated[str, Field(min_length=1)]
    right_table: Annotated[str, Field(min_length=1)]
    right_column: Annotated[str, Field(min_length=1)]
    relationship_type: Annotated[str, Field(pattern=r"^(one_to_one|one_to_many|many_to_one|many_to_many)$")]
    description: str | None = None

    @model_validator(mode="after")
    def _validate_refs(self) -> "SqlRelationshipDefinition":
        if self.left_table == self.right_table and self.left_column == self.right_column:
            raise ValueError("left and right references cannot be identical")
        return self


class SqlSchemaCatalog(BaseModel):
    """Complete approved schema catalog for SQL generation."""

    catalog_name: Annotated[str, Field(min_length=1)]
    catalog_version: str
    dialect: str = "postgresql"
    tables: tuple[SqlTableDefinition, ...]
    relationships: tuple[SqlRelationshipDefinition, ...] = ()
    global_rules: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_catalog(self) -> "SqlSchemaCatalog":
        if not self.tables:
            raise ValueError("at least one table required")
        table_names = [t.name for t in self.tables]
        if len(table_names) != len(set(table_names)):
            raise ValueError("table names must be unique")
        table_map = {t.name: t for t in self.tables}
        seen_rels = set()
        for rel in self.relationships:
            if rel.left_table not in table_map:
                raise ValueError(f"relationship references unknown left_table: {rel.left_table}")
            if rel.right_table not in table_map:
                raise ValueError(f"relationship references unknown right_table: {rel.right_table}")
            left_table = table_map[rel.left_table]
            right_table = table_map[rel.right_table]
            if not left_table.get_column(rel.left_column):
                raise ValueError(f"left_column {rel.left_column} not found in {rel.left_table}")
            if not right_table.get_column(rel.right_column):
                raise ValueError(f"right_column {rel.right_column} not found in {rel.right_table}")
            key = (rel.left_table, rel.left_column, rel.right_table, rel.right_column)
            if key in seen_rels:
                raise ValueError(f"duplicate relationship: {key}")
            seen_rels.add(key)
        return self

    def get_table(self, name: str) -> SqlTableDefinition:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(f"table not found: {name}")

    def allowed_table_names(self) -> frozenset[str]:
        return frozenset(t.name for t in self.tables if t.allowed_for_select)

    def allowed_columns(self, table_name: str) -> frozenset[str]:
        table = self.get_table(table_name)
        return frozenset(c.name for c in table.selectable_columns())

    def user_scope_columns(self, table_name: str) -> frozenset[str]:
        table = self.get_table(table_name)
        return frozenset(c.name for c in table.user_scope_columns())

    def get_relationships_for_table(self, table_name: str) -> tuple[SqlRelationshipDefinition, ...]:
        return tuple(r for r in self.relationships if r.left_table == table_name or r.right_table == table_name)


# ── SQL Pipeline Contracts (behavior-free) ─────────────────────────────────────

class SQLGenerationRequest(BaseModel):
    """Request to generate SQL from a natural-language question."""

    question: Annotated[str, Field(min_length=1, max_length=500)]
    user_id: str | int
    schema_context: str
    conversation_history: tuple[dict[str, str], ...] = ()


class GeneratedSql(BaseModel):
    """Generated SQL with metadata."""

    sql: Annotated[str, Field(min_length=1)]
    referenced_tables: tuple[str, ...] = ()
    referenced_columns: tuple[str, ...] = ()
    explanation: str | None = None
    confidence: float | None = None

    @model_validator(mode="after")
    def _validate_confidence(self) -> "GeneratedSql":
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return self


class SqlValidationError(BaseModel):
    """A single validation error found in generated SQL."""

    code: str
    message: str
    line: int | None = None
    column: int | None = None


class SqlValidationResult(BaseModel):
    """Result of validating generated SQL."""

    valid: bool
    normalized_sql: str | None = None
    referenced_tables: tuple[str, ...] = ()
    errors: tuple[SqlValidationError, ...] = ()
    warnings: tuple[str, ...] = ()


class SQLExecutionResult(BaseModel):
    """Result of executing validated SQL."""

    success: bool
    columns: tuple[str, ...] = ()
    rows: tuple[dict[str, object], ...] = ()
    row_count: int = 0
    truncated: bool = False
    execution_ms: float = 0.0
    error_code: str | None = None


class SqlEvidenceItem(BaseModel):
    """A single piece of evidence from SQL results."""

    label: str
    value: str
    source_type: str = "sql_result"


class SqlAnswerResult(BaseModel):
    """Result of generating an answer from SQL results."""

    answer: str
    evidence: tuple[SqlEvidenceItem, ...] = ()
    row_count: int = 0
    query_summary: str | None = None