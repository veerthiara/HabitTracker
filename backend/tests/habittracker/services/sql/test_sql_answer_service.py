"""Tests for habittracker.services.sql.answer_service.

All tests are pure unit tests — the ChatProvider is mocked so no LLM or
database is required.

Coverage areas:
  1. Row formatting — header, separator, values, multi-row, empty columns.
  2. Prompt construction — question and rows injected, constraints present.
  3. Empty result set — returns fallback string without calling the LLM.
  4. LLM call — provider.complete called with correct messages.
  5. LLM failure — ChatCompletionError is wrapped in SqlAnswerError.
  6. Happy path — answer text is returned stripped of leading/trailing whitespace.
  7. Singleton — module-level sql_answer_service is an SqlAnswerService instance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from habittracker.providers.base import ChatCompletionError
from habittracker.schemas.sql_chat import SqlExecutionResult
from habittracker.services.sql.answer_service import SqlAnswerService, sql_answer_service
from habittracker.services.sql.errors import SqlAnswerError


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_service(llm_response: str = "You completed 5 habits today.") -> tuple[SqlAnswerService, MagicMock]:
    """Return a service wired to a mock provider."""
    provider = MagicMock()
    provider.complete.return_value = llm_response
    return SqlAnswerService(provider=provider), provider


def _make_result(
    columns: list[str],
    rows: list[dict[str, Any]],
    sql: str = "SELECT 1",
) -> SqlExecutionResult:
    return SqlExecutionResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        sql=sql,
    )


# ── Row formatting ────────────────────────────────────────────────────────────


class TestFormatRows:

    def test_header_contains_column_names(self) -> None:
        result = _make_result(["habit", "count"], [{"habit": "Running", "count": 3}])
        text = SqlAnswerService._format_rows(result)
        assert "habit" in text
        assert "count" in text

    def test_row_values_present(self) -> None:
        result = _make_result(["name"], [{"name": "Meditation"}])
        text = SqlAnswerService._format_rows(result)
        assert "Meditation" in text

    def test_multiple_rows_all_present(self) -> None:
        result = _make_result(
            ["name"],
            [{"name": "Running"}, {"name": "Reading"}, {"name": "Yoga"}],
        )
        text = SqlAnswerService._format_rows(result)
        assert "Running" in text
        assert "Reading" in text
        assert "Yoga" in text

    def test_separator_line_present(self) -> None:
        result = _make_result(["col"], [{"col": "val"}])
        text = SqlAnswerService._format_rows(result)
        lines = text.splitlines()
        assert any(set(line.strip()) <= {"-"} for line in lines)

    def test_empty_columns_returns_no_data(self) -> None:
        result = SqlExecutionResult(columns=[], rows=[], row_count=0, sql="SELECT 1")
        assert SqlAnswerService._format_rows(result) == "(no data)"

    def test_missing_value_renders_empty_string(self) -> None:
        result = _make_result(["a", "b"], [{"a": "x"}])
        text = SqlAnswerService._format_rows(result)
        assert "x" in text

    @pytest.mark.parametrize("value", [0, None, "", False])
    def test_falsy_values_are_rendered(self, value: Any) -> None:
        result = _make_result(["val"], [{"val": value}])
        text = SqlAnswerService._format_rows(result)
        assert "val" in text


# ── Prompt construction ───────────────────────────────────────────────────────


class TestBuildSystemPrompt:

    def test_prompt_contains_question(self) -> None:
        prompt = SqlAnswerService._build_system_prompt("How many habits?", "data")
        assert "How many habits?" in prompt

    def test_prompt_contains_rows_text(self) -> None:
        prompt = SqlAnswerService._build_system_prompt("q", "habit | 3\n---\nRunning | 3")
        assert "Running | 3" in prompt

    def test_prompt_instructs_data_only(self) -> None:
        prompt = SqlAnswerService._build_system_prompt("q", "data")
        assert "ONLY" in prompt or "only" in prompt

    def test_prompt_no_sql_mention(self) -> None:
        prompt = SqlAnswerService._build_system_prompt("q", "data")
        lower = prompt.lower()
        assert "do not mention sql" in lower or "not mention sql" in lower


# ── Empty result set ──────────────────────────────────────────────────────────


class TestEmptyResultSet:

    def test_returns_fallback_without_calling_llm(self) -> None:
        svc, provider = _make_service()
        result = _make_result([], [], sql="SELECT 1")
        answer = svc.answer("How many habits?", result)
        provider.complete.assert_not_called()
        assert len(answer) > 0

    def test_fallback_is_human_readable(self) -> None:
        svc, _ = _make_service()
        result = _make_result([], [], sql="SELECT 1")
        answer = svc.answer("Any habits?", result)
        assert answer.lower() != ""
        # Should not be a raw error message or traceback
        assert "traceback" not in answer.lower()
        assert "exception" not in answer.lower()


# ── LLM call mechanics ────────────────────────────────────────────────────────


class TestLlmCall:

    def test_provider_complete_called_once(self) -> None:
        svc, provider = _make_service("You have 5 habits.")
        result = _make_result(["count"], [{"count": 5}])
        svc.answer("How many habits?", result)
        provider.complete.assert_called_once()

    def test_messages_include_system_role(self) -> None:
        svc, provider = _make_service("Done.")
        result = _make_result(["count"], [{"count": 1}])
        svc.answer("question", result)
        messages = provider.complete.call_args[0][0]
        roles = [m["role"] for m in messages]
        assert "system" in roles

    def test_messages_include_user_role(self) -> None:
        svc, provider = _make_service("Done.")
        result = _make_result(["count"], [{"count": 1}])
        svc.answer("my question", result)
        messages = provider.complete.call_args[0][0]
        user_messages = [m for m in messages if m["role"] == "user"]
        assert user_messages
        assert "my question" in user_messages[0]["content"]

    def test_system_message_contains_rows(self) -> None:
        svc, provider = _make_service("Done.")
        result = _make_result(["habit"], [{"habit": "Yoga"}])
        svc.answer("question", result)
        messages = provider.complete.call_args[0][0]
        system_content = next(m["content"] for m in messages if m["role"] == "system")
        assert "Yoga" in system_content


# ── LLM failure ───────────────────────────────────────────────────────────────


class TestLlmFailure:

    def test_chat_completion_error_raises_sql_answer_error(self) -> None:
        provider = MagicMock()
        provider.complete.side_effect = ChatCompletionError("LLM unavailable")
        svc = SqlAnswerService(provider=provider)
        result = _make_result(["count"], [{"count": 1}])
        with pytest.raises(SqlAnswerError, match="LLM call failed"):
            svc.answer("How many habits?", result)

    def test_original_exception_chained(self) -> None:
        provider = MagicMock()
        provider.complete.side_effect = ChatCompletionError("timeout")
        svc = SqlAnswerService(provider=provider)
        result = _make_result(["count"], [{"count": 1}])
        with pytest.raises(SqlAnswerError) as exc_info:
            svc.answer("q", result)
        assert exc_info.value.__cause__ is not None


# ── Happy path ────────────────────────────────────────────────────────────────


class TestAnswerHappyPath:

    def test_returns_llm_response(self) -> None:
        svc, _ = _make_service("You completed 7 habits this week.")
        result = _make_result(["count"], [{"count": 7}])
        answer = svc.answer("How many this week?", result)
        assert answer == "You completed 7 habits this week."

    def test_answer_stripped_of_whitespace(self) -> None:
        svc, _ = _make_service("  Answer with spaces.  ")
        result = _make_result(["count"], [{"count": 1}])
        answer = svc.answer("q", result)
        assert answer == "Answer with spaces."

    def test_answer_is_string(self) -> None:
        svc, _ = _make_service("Some answer.")
        result = _make_result(["x"], [{"x": 1}])
        assert isinstance(svc.answer("q", result), str)


# ── Singleton ─────────────────────────────────────────────────────────────────


class TestSingleton:

    def test_module_singleton_is_instance(self) -> None:
        assert isinstance(sql_answer_service, SqlAnswerService)
