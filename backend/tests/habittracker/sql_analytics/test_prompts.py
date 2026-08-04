"""Tests for SQL generation prompt builder."""

import pytest
from habittracker.sql_analytics.prompts import build_sql_generation_messages, SQL_GENERATION_SYSTEM_PROMPT
from habittracker.sql_analytics.contracts import SqlGenerationRequest


class TestBuildSqlGenerationMessages:
    def test_basic_message_structure(self):
        """Basic message includes system prompt, schema context, and question."""
        request = SqlGenerationRequest(
            question="How many orders?",
            user_id="user-123",
            schema_context="Table: customers\nColumns: id (uuid)...",
        )
        messages = build_sql_generation_messages(request)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SQL_GENERATION_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert "How many orders?" in messages[1]["content"]
        assert ":user_id" in messages[1]["content"]

    def test_includes_schema_context(self):
        """Schema context is included in user message."""
        request = SqlGenerationRequest(
            question="Count orders",
            user_id="u1",
            schema_context="Table: orders\nColumns: id, total",
        )
        messages = build_sql_generation_messages(request)

        user_msg = messages[1]["content"]
        assert "Table: orders" in user_msg
        assert "Columns: id, total" in user_msg

    def test_includes_user_id_binding(self):
        """User message includes :user_id binding instruction."""
        request = SqlGenerationRequest(
            question="Count orders",
            user_id="user-456",
            schema_context="...",
        )
        messages = build_sql_generation_messages(request)

        assert ":user_id" in messages[1]["content"]

    def test_includes_conversation_history(self):
        """Prior conversation turns are included as user/assistant messages."""
        history = (
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": "Another question"},
        )
        request = SqlGenerationRequest(
            question="Current question",
            user_id="u1",
            schema_context="...",
            conversation_history=history,
        )
        messages = build_sql_generation_messages(request)

        # Should have: system + 3 history + current = 5 messages
        assert len(messages) == 5
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Previous answer"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Another question"
        assert messages[4]["role"] == "user"
        assert "Current question" in messages[4]["content"]

    def test_ignores_invalid_history_roles(self):
        """History entries with invalid roles are skipped."""
        history = (
            {"role": "system", "content": "Should be skipped"},
            {"role": "invalid", "content": "Skipped"},
            {"role": "user", "content": "Valid"},
            {"role": "assistant", "content": "Also valid"},
        )
        request = SqlGenerationRequest(
            question="Question",
            user_id="u1",
            schema_context="...",
            conversation_history=history,
        )
        messages = build_sql_generation_messages(request)

        # system + 2 valid history + current = 4 messages
        assert len(messages) == 4
        assert messages[1]["content"] == "Valid"
        assert messages[2]["content"] == "Also valid"

    def test_ignores_history_without_content(self):
        """History entries missing content are skipped."""
        history = (
            {"role": "user", "content": ""},
            {"role": "user", "content": "Valid"},
        )
        request = SqlGenerationRequest(
            question="Q",
            user_id="u1",
            schema_context="...",
            conversation_history=history,
        )
        messages = build_sql_generation_messages(request)

        assert len(messages) == 3
        assert messages[1]["content"] == "Valid"

    def test_system_prompt_contains_key_constraints(self):
        """System prompt mentions critical constraints."""
        assert "EXACTLY ONE SELECT" in SQL_GENERATION_SYSTEM_PROMPT
        assert ":user_id" in SQL_GENERATION_SYSTEM_PROMPT
        assert "No INSERT" in SQL_GENERATION_SYSTEM_PROMPT
        assert "UPDATE" in SQL_GENERATION_SYSTEM_PROMPT
        assert "DELETE" in SQL_GENERATION_SYSTEM_PROMPT
        assert "LIMIT" in SQL_GENERATION_SYSTEM_PROMPT
        assert "JSON" in SQL_GENERATION_SYSTEM_PROMPT
        assert "UNTRUSTED CANDIDATE" in SQL_GENERATION_SYSTEM_PROMPT

    def test_output_is_tuple(self):
        """Return type is tuple of message dicts."""
        request = SqlGenerationRequest(question="Q", user_id="u", schema_context="...")
        messages = build_sql_generation_messages(request)

        assert isinstance(messages, tuple)
        for msg in messages:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert "content" in msg

    def test_empty_history_is_empty_tuple(self):
        """Empty history produces correct message count."""
        request = SqlGenerationRequest(question="Q", user_id="u", schema_context="...")
        messages = build_sql_generation_messages(request)
        assert len(messages) == 2  # system + user


class TestSystemPromptImmutable:
    """Ensure system prompt is a constant and not modified."""

    def test_is_string_constant(self):
        assert isinstance(SQL_GENERATION_SYSTEM_PROMPT, str)
        assert len(SQL_GENERATION_SYSTEM_PROMPT) > 100