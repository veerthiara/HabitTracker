"""Tests for habittracker.services.sql.repair_service.

All tests are pure unit tests — the ChatProvider and SqlSchemaService are
mocked so no LLM or database is required.

Coverage areas:
  1. Happy path — valid LLM response returns clean SQL.
  2. Markdown fences — ```sql ... ``` and ``` ... ``` are stripped.
  3. Empty response — raises SqlRepairError.
  4. UNSUPPORTED signal — raises SqlRepairError.
  5. LLM failure — ChatCompletionError is wrapped in SqlRepairError.
  6. Prompt contents — schema, failed SQL, and DB error are all present.
  7. Singleton — sql_repair_service is importable from the module.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from habittracker.providers.base import ChatCompletionError
from habittracker.services.sql.errors import SqlRepairError
from habittracker.services.sql.repair_service import SqlRepairService, sql_repair_service

_FAILED_SQL = "SELECT T1.volume_ml FROM bottle_events AS T1 WHERE T1.user_id = :user_id"
_DB_ERROR = "column t1.volume_ml does not exist"
_QUESTION = "How much water did I drink last week?"
_REPAIRED_SQL = (
    "SELECT SUM(bottle_events.volume_ml) FROM bottle_events "
    "WHERE bottle_events.user_id = :user_id "
    "AND bottle_events.event_ts >= NOW() - INTERVAL '7 days' LIMIT 200"
)


def _make_service(llm_response: str = _REPAIRED_SQL) -> tuple[SqlRepairService, MagicMock]:
    provider = MagicMock()
    provider.complete.return_value = llm_response
    schema_svc = MagicMock()
    schema_svc.get_summary.return_value = "-- schema --"
    return SqlRepairService(provider=provider, schema_svc=schema_svc), provider


class TestRepairHappyPath:

    def test_returns_clean_sql(self) -> None:
        svc, _ = _make_service(_REPAIRED_SQL)
        result = svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        assert result == _REPAIRED_SQL

    def test_trims_whitespace(self) -> None:
        svc, _ = _make_service(f"  {_REPAIRED_SQL}  ")
        result = svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        assert result == _REPAIRED_SQL

    def test_strips_sql_fence(self) -> None:
        svc, _ = _make_service(f"```sql\n{_REPAIRED_SQL}\n```")
        result = svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        assert result == _REPAIRED_SQL

    def test_strips_plain_fence(self) -> None:
        svc, _ = _make_service(f"```\n{_REPAIRED_SQL}\n```")
        result = svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        assert result == _REPAIRED_SQL


class TestRepairFailureCases:

    def test_empty_response_raises(self) -> None:
        svc, _ = _make_service("   ")
        with pytest.raises(SqlRepairError, match="empty"):
            svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)

    def test_unsupported_signal_raises(self) -> None:
        svc, _ = _make_service("UNSUPPORTED")
        with pytest.raises(SqlRepairError):
            svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)

    def test_llm_exception_wrapped(self) -> None:
        svc, provider = _make_service()
        provider.complete.side_effect = ChatCompletionError("timeout")
        with pytest.raises(SqlRepairError, match="LLM call failed"):
            svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)


class TestRepairPromptContents:
    """The prompt sent to the LLM must include the schema, failed SQL, and DB error."""

    def test_prompt_contains_schema(self) -> None:
        svc, provider = _make_service()
        svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        prompt_text = provider.complete.call_args[0][0][0]["content"]
        assert "-- schema --" in prompt_text

    def test_prompt_contains_failed_sql(self) -> None:
        svc, provider = _make_service()
        svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        prompt_text = provider.complete.call_args[0][0][0]["content"]
        assert _FAILED_SQL in prompt_text

    def test_prompt_contains_db_error(self) -> None:
        svc, provider = _make_service()
        svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        prompt_text = provider.complete.call_args[0][0][0]["content"]
        assert _DB_ERROR in prompt_text

    def test_prompt_contains_question(self) -> None:
        svc, provider = _make_service()
        svc.repair(_QUESTION, _FAILED_SQL, _DB_ERROR)
        prompt_text = provider.complete.call_args[0][0][0]["content"]
        assert _QUESTION in prompt_text


class TestSingleton:
    def test_singleton_is_instance(self) -> None:
        assert isinstance(sql_repair_service, SqlRepairService)
