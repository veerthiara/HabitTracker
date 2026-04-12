"""Tests for habittracker.services.sql.generation_service.

All tests are pure unit tests — the ChatProvider and SqlSchemaService are
mocked so no LLM or database is required.

Coverage areas:
  1. Prompt construction — system prompt contains the schema summary.
  2. SQL extraction — clean bare SQL, markdown code fences (``` and ```sql),
     leading/trailing whitespace all produce correct output.
  3. UNSUPPORTED signal — LLM returning "UNSUPPORTED" raises SqlGenerationError.
  4. Empty response — raises SqlGenerationError.
  5. LLM failure — ChatCompletionError is wrapped in SqlGenerationError.
  6. Happy path — valid response returns SqlGenerationResult with correct fields.
  7. user_id forwarded — result carries the original user_id unchanged.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from habittracker.providers.base import ChatCompletionError
from habittracker.schemas.sql_chat import SqlGenerationRequest, SqlGenerationResult
from habittracker.services.sql.errors import SqlGenerationError
from habittracker.services.sql.generation_service import SqlGenerationService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_service(llm_response: str = "SELECT 1") -> tuple[SqlGenerationService, MagicMock]:
    """Return a service wired to a mock provider and a mock schema service."""
    provider = MagicMock()
    provider.complete.return_value = llm_response

    schema_svc = MagicMock()
    schema_svc.get_summary.return_value = "-- schema summary --"

    return SqlGenerationService(provider=provider, schema_svc=schema_svc), provider


def _req(question: str = "How many habits do I have?", user_id: str | None = None) -> SqlGenerationRequest:
    return SqlGenerationRequest(
        question=question,
        user_id=user_id or str(uuid.uuid4()),
    )


# ── Prompt construction ───────────────────────────────────────────────────────


class TestBuildSystemPrompt:

    def test_prompt_contains_schema(self) -> None:
        prompt = SqlGenerationService._build_system_prompt("TABLE: habits")
        assert "TABLE: habits" in prompt

    def test_prompt_mentions_user_id_param(self) -> None:
        prompt = SqlGenerationService._build_system_prompt("")
        assert ":user_id" in prompt

    def test_prompt_mentions_select_only(self) -> None:
        prompt = SqlGenerationService._build_system_prompt("")
        assert "SELECT" in prompt

    def test_prompt_mentions_unsupported_signal(self) -> None:
        prompt = SqlGenerationService._build_system_prompt("")
        assert "UNSUPPORTED" in prompt


# ── SQL extraction ────────────────────────────────────────────────────────────


class TestExtractSql:

    def test_bare_sql_returned_as_is(self) -> None:
        sql = "SELECT id FROM habits WHERE user_id = :user_id"
        assert SqlGenerationService._extract_sql(sql) == sql

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert SqlGenerationService._extract_sql("  SELECT 1  ") == "SELECT 1"

    def test_strips_plain_code_fence(self) -> None:
        raw = "```\nSELECT id FROM habits\n```"
        assert SqlGenerationService._extract_sql(raw) == "SELECT id FROM habits"

    def test_strips_sql_code_fence(self) -> None:
        raw = "```sql\nSELECT id FROM habits\n```"
        assert SqlGenerationService._extract_sql(raw) == "SELECT id FROM habits"

    def test_strips_sql_fence_case_insensitive(self) -> None:
        raw = "```SQL\nSELECT 1\n```"
        assert SqlGenerationService._extract_sql(raw) == "SELECT 1"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(SqlGenerationError, match="empty"):
            SqlGenerationService._extract_sql("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(SqlGenerationError, match="empty"):
            SqlGenerationService._extract_sql("   ")

    def test_unsupported_raises(self) -> None:
        with pytest.raises(SqlGenerationError, match="cannot be answered"):
            SqlGenerationService._extract_sql("UNSUPPORTED")

    def test_unsupported_case_insensitive(self) -> None:
        with pytest.raises(SqlGenerationError):
            SqlGenerationService._extract_sql("unsupported")


# ── generate() happy path ─────────────────────────────────────────────────────


class TestGenerateHappyPath:

    def test_returns_generation_result(self) -> None:
        svc, _ = _make_service("SELECT id FROM habits WHERE user_id = :user_id")
        result = svc.generate(_req())
        assert isinstance(result, SqlGenerationResult)

    def test_result_sql_matches_llm_output(self) -> None:
        expected = "SELECT id FROM habits WHERE user_id = :user_id"
        svc, _ = _make_service(expected)
        result = svc.generate(_req())
        assert result.sql == expected

    def test_question_forwarded(self) -> None:
        svc, _ = _make_service()
        q = "Which habit do I miss most?"
        result = svc.generate(_req(question=q))
        assert result.question == q

    def test_user_id_forwarded(self) -> None:
        svc, _ = _make_service()
        uid = str(uuid.uuid4())
        result = svc.generate(_req(user_id=uid))
        assert result.user_id == uid

    def test_provider_called_with_two_messages(self) -> None:
        svc, provider = _make_service()
        svc.generate(_req())
        messages = provider.complete.call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_prompt_contains_schema(self) -> None:
        svc, provider = _make_service()
        svc.generate(_req())
        system_content = provider.complete.call_args[0][0][0]["content"]
        assert "-- schema summary --" in system_content

    def test_user_message_is_the_question(self) -> None:
        svc, provider = _make_service()
        q = "How many habits did I complete this week?"
        svc.generate(_req(question=q))
        user_content = provider.complete.call_args[0][0][1]["content"]
        assert user_content == q

    def test_fenced_sql_stripped_from_result(self) -> None:
        svc, _ = _make_service("```sql\nSELECT id FROM habits\n```")
        result = svc.generate(_req())
        assert result.sql == "SELECT id FROM habits"


# ── generate() failure paths ──────────────────────────────────────────────────


class TestGenerateFailures:

    def test_llm_error_raises_generation_error(self) -> None:
        svc, provider = _make_service()
        provider.complete.side_effect = ChatCompletionError("timeout")
        with pytest.raises(SqlGenerationError, match="LLM call failed"):
            svc.generate(_req())

    def test_unsupported_response_raises_generation_error(self) -> None:
        svc, _ = _make_service("UNSUPPORTED")
        with pytest.raises(SqlGenerationError):
            svc.generate(_req())

    def test_empty_response_raises_generation_error(self) -> None:
        svc, _ = _make_service("")
        with pytest.raises(SqlGenerationError):
            svc.generate(_req())
