"""Tests for habittracker.services.sql.pipeline_service.

All tests are unit tests — generation, validation, and execution services are
all mocked so no LLM or database is required.

Coverage areas:
  1. Happy path — all stages succeed → success=True, execution result present.
  2. Generation failure — SqlGenerationError → success=False, failure_reason set.
  3. Validation rejection — REJECTED → success=False, failure_reason set,
     execution stage NOT called.
  4. Execution failure — SqlExecutionError → success=False, failure_reason set.
  5. Result fields — question and generated_sql are always forwarded correctly.
  6. Never raises — all failure paths return a result rather than raising.
  7. Singleton — sql_pipeline_service is accessible from the module.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from habittracker.schemas.sql_chat import (
    SqlExecutionResult,
    SqlGenerationRequest,
    SqlGenerationResult,
    SqlPipelineResult,
    SqlValidationResult,
    ValidationStatus,
)
from habittracker.services.sql.errors import SqlExecutionError, SqlGenerationError
from habittracker.services.sql.pipeline_service import SqlPipelineService, sql_pipeline_service


# ── Helpers ───────────────────────────────────────────────────────────────────


_FAKE_SQL = "SELECT id FROM habits WHERE user_id = :user_id LIMIT 10"
_FAKE_QUESTION = "How many habits do I have?"
_FAKE_USER_ID = str(uuid.uuid4())


def _make_request(
    question: str = _FAKE_QUESTION,
    user_id: str = _FAKE_USER_ID,
) -> SqlGenerationRequest:
    return SqlGenerationRequest(question=question, user_id=user_id)


def _make_generation_result(
    sql: str = _FAKE_SQL,
    question: str = _FAKE_QUESTION,
    user_id: str = _FAKE_USER_ID,
) -> SqlGenerationResult:
    return SqlGenerationResult(sql=sql, question=question, user_id=user_id)


def _make_ok_validation(sql: str = _FAKE_SQL) -> SqlValidationResult:
    return SqlValidationResult(status=ValidationStatus.OK, sql=sql)


def _make_rejected_validation(
    sql: str = _FAKE_SQL,
    reason: str = "Not a SELECT statement.",
) -> SqlValidationResult:
    return SqlValidationResult(
        status=ValidationStatus.REJECTED,
        sql=sql,
        rejection_reason=reason,
    )


def _make_execution_result(sql: str = _FAKE_SQL) -> SqlExecutionResult:
    return SqlExecutionResult(
        columns=["id"],
        rows=[{"id": "abc"}],
        row_count=1,
        sql=sql,
    )


def _make_pipeline(
    generation_result: SqlGenerationResult | Exception | None = None,
    validation_result: SqlValidationResult | None = None,
    execution_result: SqlExecutionResult | Exception | None = None,
) -> SqlPipelineService:
    """Build a SqlPipelineService with fully mocked dependencies."""
    generation_svc = MagicMock()
    if isinstance(generation_result, Exception):
        generation_svc.generate.side_effect = generation_result
    else:
        generation_svc.generate.return_value = generation_result or _make_generation_result()

    validation_svc = MagicMock()
    validation_svc.validate.return_value = validation_result or _make_ok_validation()

    execution_svc = MagicMock()
    if isinstance(execution_result, Exception):
        execution_svc.execute.side_effect = execution_result
    else:
        execution_svc.execute.return_value = execution_result or _make_execution_result()

    return SqlPipelineService(
        generation_svc=generation_svc,
        validation_svc=validation_svc,
        execution_svc=execution_svc,
    )


# ── Happy path ────────────────────────────────────────────────────────────────


class TestHappyPath:

    def test_returns_success(self) -> None:
        svc = _make_pipeline()
        result = svc.run(_make_request(), session=MagicMock())
        assert result.success is True

    def test_execution_result_present(self) -> None:
        exec_result = _make_execution_result()
        svc = _make_pipeline(execution_result=exec_result)
        result = svc.run(_make_request(), session=MagicMock())
        assert result.execution is not None
        assert result.execution.row_count == 1

    def test_question_forwarded(self) -> None:
        svc = _make_pipeline()
        result = svc.run(_make_request(question="custom question?"), session=MagicMock())
        assert result.question == "custom question?"

    def test_generated_sql_forwarded(self) -> None:
        custom_sql = "SELECT name FROM habits WHERE user_id = :user_id"
        svc = _make_pipeline(
            generation_result=_make_generation_result(sql=custom_sql),
            validation_result=_make_ok_validation(sql=custom_sql),
            execution_result=_make_execution_result(sql=custom_sql),
        )
        result = svc.run(_make_request(), session=MagicMock())
        assert result.generated_sql == custom_sql

    def test_failure_reason_none_on_success(self) -> None:
        svc = _make_pipeline()
        result = svc.run(_make_request(), session=MagicMock())
        assert result.failure_reason is None

    def test_validation_ok_status_forwarded(self) -> None:
        svc = _make_pipeline()
        result = svc.run(_make_request(), session=MagicMock())
        assert result.validation.status == ValidationStatus.OK


# ── Generation failure ────────────────────────────────────────────────────────


class TestGenerationFailure:

    def test_returns_failure(self) -> None:
        svc = _make_pipeline(generation_result=SqlGenerationError("LLM error"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.success is False

    def test_failure_reason_set(self) -> None:
        svc = _make_pipeline(generation_result=SqlGenerationError("LLM error"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.failure_reason is not None
        assert "generation" in result.failure_reason.lower()

    def test_execution_not_called(self) -> None:
        gen_svc = MagicMock()
        gen_svc.generate.side_effect = SqlGenerationError("LLM error")
        val_svc = MagicMock()
        exec_svc = MagicMock()
        svc = SqlPipelineService(
            generation_svc=gen_svc,
            validation_svc=val_svc,
            execution_svc=exec_svc,
        )
        svc.run(_make_request(), session=MagicMock())
        exec_svc.execute.assert_not_called()

    def test_generated_sql_empty(self) -> None:
        svc = _make_pipeline(generation_result=SqlGenerationError("LLM error"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.generated_sql == ""

    def test_question_still_forwarded(self) -> None:
        svc = _make_pipeline(generation_result=SqlGenerationError("LLM error"))
        result = svc.run(_make_request(question="my question"), session=MagicMock())
        assert result.question == "my question"


# ── Validation rejection ──────────────────────────────────────────────────────


class TestValidationRejection:

    def test_returns_failure(self) -> None:
        svc = _make_pipeline(validation_result=_make_rejected_validation())
        result = svc.run(_make_request(), session=MagicMock())
        assert result.success is False

    def test_failure_reason_from_rejection(self) -> None:
        svc = _make_pipeline(
            validation_result=_make_rejected_validation(reason="Forbidden keyword DROP found.")
        )
        result = svc.run(_make_request(), session=MagicMock())
        assert "Forbidden keyword DROP found." in result.failure_reason

    def test_execution_not_called(self) -> None:
        gen_svc = MagicMock()
        gen_svc.generate.return_value = _make_generation_result()
        val_svc = MagicMock()
        val_svc.validate.return_value = _make_rejected_validation()
        exec_svc = MagicMock()
        svc = SqlPipelineService(
            generation_svc=gen_svc,
            validation_svc=val_svc,
            execution_svc=exec_svc,
        )
        svc.run(_make_request(), session=MagicMock())
        exec_svc.execute.assert_not_called()

    def test_execution_result_none(self) -> None:
        svc = _make_pipeline(validation_result=_make_rejected_validation())
        result = svc.run(_make_request(), session=MagicMock())
        assert result.execution is None

    def test_generated_sql_still_present(self) -> None:
        svc = _make_pipeline(
            generation_result=_make_generation_result(sql=_FAKE_SQL),
            validation_result=_make_rejected_validation(sql=_FAKE_SQL),
        )
        result = svc.run(_make_request(), session=MagicMock())
        assert result.generated_sql == _FAKE_SQL


# ── Execution failure ─────────────────────────────────────────────────────────


class TestExecutionFailure:

    def test_returns_failure(self) -> None:
        svc = _make_pipeline(execution_result=SqlExecutionError("DB timeout"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.success is False

    def test_failure_reason_set(self) -> None:
        svc = _make_pipeline(execution_result=SqlExecutionError("DB timeout"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.failure_reason is not None
        assert "execution" in result.failure_reason.lower()

    def test_execution_result_none(self) -> None:
        svc = _make_pipeline(execution_result=SqlExecutionError("DB timeout"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.execution is None

    def test_validation_result_still_present(self) -> None:
        svc = _make_pipeline(execution_result=SqlExecutionError("DB timeout"))
        result = svc.run(_make_request(), session=MagicMock())
        assert result.validation.status == ValidationStatus.OK


# ── Never raises ──────────────────────────────────────────────────────────────


class TestNeverRaises:

    @pytest.mark.parametrize("exc", [
        SqlGenerationError("gen fail"),
        SqlExecutionError("exec fail"),
    ])
    def test_does_not_raise(self, exc: Exception) -> None:
        if isinstance(exc, SqlGenerationError):
            svc = _make_pipeline(generation_result=exc)
        else:
            svc = _make_pipeline(execution_result=exc)
        # Must not raise
        result = svc.run(_make_request(), session=MagicMock())
        assert isinstance(result, SqlPipelineResult)


# ── Module singleton ──────────────────────────────────────────────────────────


class TestSingleton:

    def test_singleton_is_accessible(self) -> None:
        assert sql_pipeline_service is not None

    def test_singleton_is_pipeline_service(self) -> None:
        assert isinstance(sql_pipeline_service, SqlPipelineService)
