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
    GenerationMethod,
    SqlExecutionRequest,
    SqlGenerationRequest,
    SqlPipelineResult,
    SqlValidationResult,
    ValidationStatus,
)
from habittracker.services.sql.answer_service import SqlAnswerService, sql_answer_service
from habittracker.services.sql.errors import (
    SqlAnswerError,
    SqlExecutionError,
    SqlGenerationError,
    SqlParameterExtractionError,
    SqlRepairError,
    SqlTemplateError,
)
from habittracker.services.sql.execution_service import SqlExecutionService, sql_execution_service
from habittracker.services.sql.generation_service import SqlGenerationService, sql_generation_service
from habittracker.services.sql.intent_classifier import SqlIntentClassifier, sql_intent_classifier
from habittracker.services.sql.parameter_extractor import SqlParameterExtractor, sql_parameter_extractor
from habittracker.services.sql.repair_service import SqlRepairService, sql_repair_service
from habittracker.services.sql.template_renderer import SqlTemplateRenderer, sql_template_renderer
from habittracker.services.sql.validation_service import SqlValidationService, sql_validation_service
from habittracker.schemas.sql_template import SqlAnalyticsIntent

logger = logging.getLogger(__name__)


class SqlPipelineService:
    """Runs the full generation → validation → execution pipeline.

    Stage 1 (generation) tries the template path first:
      a) classify the question with SqlIntentClassifier
      b) if a known intent → extract parameters with SqlParameterExtractor
         → render a fixed SQL template with SqlTemplateRenderer
      c) if UNKNOWN intent, or if template extraction/render fails →
         fall back to free-form LLM generation via SqlGenerationService

    Stage 3 (execution) catches DB errors and attempts one repair pass
    via SqlRepairService.  If the repaired SQL also fails, a safe fallback
    message is returned to the user.

    Dependencies are injected so they can be easily swapped in tests.
    """

    def __init__(
        self,
        generation_svc: SqlGenerationService,
        validation_svc: SqlValidationService,
        execution_svc: SqlExecutionService,
        answer_svc: SqlAnswerService,
        intent_classifier: SqlIntentClassifier,
        parameter_extractor: SqlParameterExtractor,
        template_renderer: SqlTemplateRenderer,
        repair_svc: SqlRepairService,
    ) -> None:
        self._generation_svc = generation_svc
        self._validation_svc = validation_svc
        self._execution_svc = execution_svc
        self._answer_svc = answer_svc
        self._intent_classifier = intent_classifier
        self._parameter_extractor = parameter_extractor
        self._template_renderer = template_renderer
        self._repair_svc = repair_svc

    # ── Private helpers ───────────────────────────────────────────────────────

    def _generate_sql(
        self, request: SqlGenerationRequest
    ) -> tuple[str, GenerationMethod]:
        """Attempt template-backed generation; fall back to LLM.

        Returns:
            (sql_text, generation_method)

        Raises:
            SqlGenerationError: Both template and LLM generation failed.
        """
        intent = self._intent_classifier.classify(request.question)

        if intent != SqlAnalyticsIntent.UNKNOWN:
            try:
                params = self._parameter_extractor.extract(request.question, intent)
                sql = self._template_renderer.render(params)
                logger.info(
                    "SQL generated from template: intent=%s  sql=%r",
                    intent,
                    sql,
                )
                return sql, GenerationMethod.TEMPLATE
            except (SqlParameterExtractionError, SqlTemplateError) as exc:
                logger.warning(
                    "Template path failed (%s), falling back to LLM: %s",
                    intent,
                    exc,
                )

        # LLM fallback
        result = self._generation_svc.generate(request)
        logger.info("SQL generated by LLM: %r", result.sql)
        return result.sql, GenerationMethod.LLM

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        request: SqlGenerationRequest,
        session: Session,
    ) -> SqlPipelineResult:
        """Run the full pipeline and return a SqlPipelineResult.

        Never raises.  Any failure is encoded in the result with
        success=False and a failure_reason.
        """
        # ── Stage 1: generate ─────────────────────────────────────────────────
        try:
            generated_sql, generation_method = self._generate_sql(request)
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
                generation_method=generation_method,
            )

        # ── Stage 3: execute (with one-pass repair on failure) ────────────────
        execution_result, repair_attempted, repair_error = self._execute_with_repair(
            sql=generated_sql,
            request=request,
            session=session,
        )

        if execution_result is None:
            return SqlPipelineResult(
                question=request.question,
                generated_sql=generated_sql,
                validation=validation_result,
                success=False,
                failure_reason=repair_error or "SQL execution failed.",
                generation_method=generation_method,
                repair_attempted=repair_attempted,
                repair_error=repair_error,
            )

        # ── Stage 4: answer ───────────────────────────────────────────────────
        try:
            answer_text = self._answer_svc.answer(request.question, execution_result)
        except SqlAnswerError as exc:
            logger.warning("SQL answer generation failed: %s", exc)
            return SqlPipelineResult(
                question=request.question,
                generated_sql=generated_sql,
                validation=validation_result,
                execution=execution_result,
                success=False,
                failure_reason=f"Answer generation failed: {exc}",
                generation_method=generation_method,
            )

        return SqlPipelineResult(
            question=request.question,
            generated_sql=generated_sql,
            validation=validation_result,
            execution=execution_result,
            success=True,
            answer=answer_text,
            generation_method=generation_method,
            repair_attempted=repair_attempted,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _execute_with_repair(
        self,
        sql: str,
        request: SqlGenerationRequest,
        session,
    ) -> tuple:
        """Attempt execution; on failure try one repair pass.

        Returns:
            (execution_result, repair_attempted, repair_error)
            execution_result is None when both attempts failed.
        """
        exec_request = SqlExecutionRequest(sql=sql, user_id=request.user_id)
        try:
            return self._execution_svc.execute(exec_request, session), False, None
        except SqlExecutionError as first_exc:
            db_error = str(first_exc)
            logger.warning("SQL execution failed (will attempt repair): %s", db_error)

        # ── Repair attempt ────────────────────────────────────────────────────
        try:
            repaired_sql = self._repair_svc.repair(
                question=request.question,
                failed_sql=sql,
                db_error=db_error,
            )
        except SqlRepairError as exc:
            failure = f"SQL execution failed and repair was not possible: {exc}"
            logger.warning("SQL repair failed: %s", exc)
            return None, True, failure

        # Validate the repaired SQL before re-executing
        repair_validation = self._validation_svc.validate(repaired_sql)
        if repair_validation.status == ValidationStatus.REJECTED:
            failure = (
                f"Repaired SQL was rejected by validator: "
                f"{repair_validation.rejection_reason}"
            )
            logger.warning(failure)
            return None, True, failure

        repaired_exec = SqlExecutionRequest(sql=repaired_sql, user_id=request.user_id)
        try:
            result = self._execution_svc.execute(repaired_exec, session)
            logger.info("SQL repair succeeded.")
            return result, True, None
        except SqlExecutionError as second_exc:
            failure = (
                f"SQL execution failed after repair attempt. "
                f"Original: {db_error}. After repair: {second_exc}"
            )
            logger.warning(failure)
            return None, True, failure


# ── Module-level singleton ────────────────────────────────────────────────────

sql_pipeline_service = SqlPipelineService(
    generation_svc=sql_generation_service,
    validation_svc=sql_validation_service,
    execution_svc=sql_execution_service,
    answer_svc=sql_answer_service,
    intent_classifier=sql_intent_classifier,
    parameter_extractor=sql_parameter_extractor,
    template_renderer=sql_template_renderer,
    repair_svc=sql_repair_service,
)
