"""Internal request/response contracts for the SQL analytics path.

These schemas are used internally between services (generation →
validation → execution → answer).  They are NOT exposed directly on
the public API — the public chat endpoint continues to use ChatResponse.

Pydantic models are used here so that:
  - each service has a typed, validated contract with the next stage
  - test assertions can use model fields rather than raw dicts
  - future serialisation (e.g. Langfuse metadata) is straightforward
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── SQL generation ─────────────────────────────────────────────────────────────


class SqlGenerationRequest(BaseModel):
    """Input to the SQL generation service."""

    question: str = Field(..., description="Natural-language analytical question from the user.")
    user_id: str = Field(..., description="UUID of the authenticated user; used to scope all queries.")


class GenerationMethod(str, Enum):
    TEMPLATE = "template"
    LLM = "llm"


class SqlGenerationResult(BaseModel):
    """Output from the SQL generation service."""

    sql: str = Field(..., description="Generated SQL text (SELECT only).")
    question: str = Field(..., description="Original question, carried forward for context.")
    user_id: str = Field(..., description="User ID, carried forward for execution scoping.")
    generation_method: GenerationMethod = Field(
        default=GenerationMethod.LLM,
        description="Whether SQL was produced by a fixed template or free-form LLM generation.",
    )


# ── SQL validation ─────────────────────────────────────────────────────────────


class ValidationStatus(str, Enum):
    OK = "ok"
    REJECTED = "rejected"


class SqlValidationResult(BaseModel):
    """Result of static safety validation performed before execution."""

    status: ValidationStatus
    sql: str = Field(..., description="SQL that was validated.")
    rejection_reason: str | None = Field(
        default=None,
        description="Human-readable reason when status=rejected.",
    )


# ── SQL execution ──────────────────────────────────────────────────────────────


class SqlExecutionRequest(BaseModel):
    """Input to the SQL execution service."""

    sql: str = Field(..., description="Validated SQL text to execute.")
    user_id: str = Field(..., description="User ID injected as a bind parameter.")


class SqlExecutionResult(BaseModel):
    """Structured output from one SQL query execution."""

    columns: list[str] = Field(..., description="Ordered list of column names returned.")
    rows: list[dict[str, Any]] = Field(..., description="Result rows as column→value dicts.")
    row_count: int = Field(..., description="Number of rows in the result set.")
    sql: str = Field(..., description="The SQL that was executed, for debug/logging.")


# ── End-to-end pipeline result ─────────────────────────────────────────────────


class SqlPipelineResult(BaseModel):
    """Aggregated result from the full text-to-SQL pipeline.

    Passed to the answer-generation service and optionally surfaced as
    Langfuse metadata in development mode.
    """

    question: str
    generated_sql: str
    validation: SqlValidationResult
    execution: SqlExecutionResult | None = Field(
        default=None,
        description="None when validation rejected the query.",
    )
    success: bool = Field(
        ...,
        description="True when validation passed AND execution returned rows.",
    )
    failure_reason: str | None = Field(
        default=None,
        description="Short reason string when success=False.",
    )
    answer: str | None = Field(
        default=None,
        description="Natural-language answer generated from the execution rows. None when the pipeline did not reach the answer stage.",
    )
    generation_method: GenerationMethod | None = Field(
        default=None,
        description="How the SQL was produced: 'template' or 'llm'. None when generation did not complete.",
    )
    repair_attempted: bool = Field(
        default=False,
        description="True when the repair loop was invoked after an execution failure.",
    )
    repair_error: str | None = Field(
        default=None,
        description="Reason the repair attempt failed, if repair_attempted=True and success=False.",
    )
