"""SQL pipeline service — SqlPipelineService.

SqlPipelineService orchestrates the full text-to-SQL pipeline:

  1. Generate SQL from the user's natural-language question
     (SqlGenerationService)
  2. Validate the generated SQL against static safety rules
     (SqlValidationService)
  3. Execute the validated SQL against the database
     (SqlExecutionService)

The service never raises.  Every possible failure is caught and encoded
in a SqlPipelineResult with success=False and a human-readable
failure_reason.  This makes it safe for the chat layer to call without a
try/except.

Design:
  - Class-based service; all dependencies injected at construction time.
  - sql_pipeline_service is the module-level singleton wired to the three
    production singletons.
  - Each pipeline stage is a distinct method so tests can override only
    the behaviour they care about.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from habittracker.schemas.sql_chat import (
    SqlExecutionRequest,
    SqlGenerationRequest,
    SqlPipelineResult,
    SqlValidationResult,
    ValidationStatus,
)
from habittracker.services.sql.errors import SqlExecutionError, SqlGenerationError
from habittracker.services.sql.execution_service import SqlExecutionService, sql_execution_service
from habittracker.services.sql.generation_service import SqlGenerationService, sql_generation_service
from habittracker.services.sql.validation_service import SqlValidationService, sql_validation_service

logger = logging.getLogger(__name__)


class SqlPipelineService:
    """Runs the full generation → validation → execution pipeline.

    Dependencies are injected so they can be easily swapped in tests.
    """

    def __init__(
        self,
        generation_svc: SqlGenerationService,
        validation_svc: SqlValidationService,
        execution_svc: SqlExecutionService,
    ) -> None:
        self._generation_svc = generation_svc
        self._validation_svc = validation_svc
        self._execution_svc = execution_svc

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        request: SqlGenerationRequest,
        session: Session,
    ) -> SqlPipelineResult:
        """Run the full pipeline and return a SqlPipelineResult.

        Never raises.  Any failure is encoded in the result with
        success=False and a failure_reason.

        Args:
            request: Contains the user's question and user_id.
            session:  Active SQLAlchemy Session for the execution stage.

        Returns:
            SqlPipelineResult aggregating all three stages.
        """
        # ── Stage 1: generate ─────────────────────────────────────────────────
        try:
            generation_result = self._generation_svc.generate(request)
        except SqlGenerationError as exc:
            logger.warning("SQL generation failed: %s", exc)
            placeholder_validation = SqlValidationResult(
                status=ValidationStatus.REJECTED,
                sql="",
                rejection_reason="SQL generation failed before validation.",
            )
            return SqlPipelineResult(
                question=request.question,
                generated_sql="",
                validation=placeholder_validation,
                success=False,
                failure_reason=f"SQL generation failed: {exc}",
            )

        generated_sql = generation_result.sql

        # ── Stage 2: validate ─────────────────────────────────────────────────
        validation_result = self._validation_svc.validate(generated_sql)

        if validation_result.status == ValidationStatus.REJECTED:
            logger.info(
                "SQL rejected by validator: %s",
                validation_result.rejection_reason,
            )
            return SqlPipelineResult(
                question=request.question,
                generated_sql=generated_sql,
                validation=validation_result,
                success=False,
                failure_reason=validation_result.rejection_reason,
            )

        # ── Stage 3: execute ──────────────────────────────────────────────────
        exec_request = SqlExecutionRequest(
            sql=generated_sql,
            user_id=request.user_id,
        )
        try:
            execution_result = self._execution_svc.execute(exec_request, session)
        except SqlExecutionError as exc:
            logger.warning("SQL execution failed: %s", exc)
            return SqlPipelineResult(
                question=request.question,
                generated_sql=generated_sql,
                validation=validation_result,
                success=False,
                failure_reason=f"SQL execution failed: {exc}",
            )

        return SqlPipelineResult(
            question=request.question,
            generated_sql=generated_sql,
            validation=validation_result,
            execution=execution_result,
            success=True,
        )


# ── Module-level singleton ────────────────────────────────────────────────────

sql_pipeline_service = SqlPipelineService(
    generation_svc=sql_generation_service,
    validation_svc=sql_validation_service,
    execution_svc=sql_execution_service,
)
