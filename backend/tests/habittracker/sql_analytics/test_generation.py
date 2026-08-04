"""Tests for SqlGenerationService."""

import pytest
from unittest.mock import MagicMock

from habittracker.providers.base import ChatProvider, ChatCompletionError
from habittracker.sql_analytics.catalog import StaticSqlCatalogProvider
from habittracker.sql_analytics.contracts import (
    GeneratedSql,
    SqlGenerationRequest,
    SqlSchemaCatalog,
    SqlTableDefinition,
    SqlColumnDefinition,
)
from habittracker.sql_analytics.generation import (
    SqlGenerationService,
    SqlGenerationResponseError,
    SqlGenerationError,
)
from habittracker.sql_analytics.renderer import SqlSchemaContextRenderer


# ── Test Fixtures ──────────────────────────────────────────────────────────────

def _fake_catalog():
    """Simple fake catalog for testing."""
    from habittracker.sql_analytics.contracts import (
        SqlSchemaCatalog,
        SqlTableDefinition,
        SqlColumnDefinition,
    )
    return SqlSchemaCatalog(
        catalog_name="test",
        catalog_version="1",
        tables=(
            SqlTableDefinition(
                name="orders",
                description="Orders table",
                user_scoped=True,
                columns=(
                    SqlColumnDefinition(name="id", description="PK", data_type="uuid", is_primary_key=True),
                    SqlColumnDefinition(name="user_id", description="Owner", data_type="uuid", is_foreign_key=True, foreign_key_target="users.id", is_user_scope=True),
                    SqlColumnDefinition(name="total", description="Total", data_type="integer", nullable=False),
                ),
            ),
            SqlTableDefinition(
                name="users",
                description="Users table",
                user_scoped=False,
                allowed_for_select=False,
                columns=(
                    SqlColumnDefinition(name="id", description="PK", data_type="uuid", is_primary_key=True),
                ),
            ),
        ),
        relationships=(),
        global_rules=("Only SELECT",),
    )


class MockChatProvider:
    """Mock chat provider for testing."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.call_count = 0
        self.last_messages = None

    def complete(self, messages: list[dict]) -> str:
        self.call_count += 1
        self.last_messages = messages
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSqlGenerationService:
    def setup_method(self):
        self.catalog = _fake_catalog()
        self.catalog_provider = StaticSqlCatalogProvider(self.catalog)
        self.renderer = SqlSchemaContextRenderer()

    def test_generate_returns_parsed_generated_sql(self):
        """Successful generation returns typed GeneratedSql."""
        provider = MockChatProvider('''{
            "sql": "SELECT * FROM orders WHERE user_id = :user_id LIMIT 100",
            "referenced_tables": ["orders"],
            "referenced_columns": ["orders.id", "orders.total"],
            "explanation": "Selects all orders for the user",
            "confidence": 0.9
        }''')

        service = SqlGenerationService(
            provider=provider,
            catalog_provider=StaticSqlCatalogProvider(_fake_catalog()),
        )

        result = service.generate("Show my orders", user_id="user-123")

        assert isinstance(result, GeneratedSql)
        assert "SELECT" in result.sql
        assert result.referenced_tables == ("orders",)
        assert result.confidence == 0.9
        assert provider.call_count == 1

    def test_provider_receives_correct_messages(self):
        """Provider receives properly structured messages."""
        provider = MockChatProvider('{"sql": "SELECT 1"}')

        service = SqlGenerationService(
            provider=provider,
            catalog_provider=StaticSqlCatalogProvider(_fake_catalog()),
        )

        service.generate("Test question", user_id="user-1")

        messages = provider.last_messages
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test question" in messages[1]["content"]
        assert ":user_id" in messages[1]["content"]

    def test_includes_conversation_history(self):
        """Conversation history is passed to provider."""
        provider = MockChatProvider('{"sql": "SELECT 1"}')

        service = SqlGenerationService(
            provider=provider,
            catalog_provider=StaticSqlCatalogProvider(_fake_catalog()),
        )

        service.generate(
            "Current question",
            user_id="u1",
            conversation_history=(
                {"role": "user", "content": "Previous Q"},
                {"role": "assistant", "content": "Previous A"},
            ),
        )

        messages = provider.last_messages
        # system + 2 history + current = 4
        assert len(messages) == 4
        assert messages[1]["content"] == "Previous Q"
        assert messages[2]["content"] == "Previous A"

    def test_raises_on_empty_question(self):
        """Empty question raises ValueError."""
        provider = MockChatProvider('{"sql": "SELECT 1"}')
        service = SqlGenerationService(provider=provider, catalog_provider=StaticSqlCatalogProvider(_fake_catalog()))

        with pytest.raises(ValueError, match="question must not be empty"):
            service.generate("", user_id="u1")

    def test_raises_on_whitespace_question(self):
        """Whitespace-only question raises ValueError."""
        provider = MockChatProvider('{"sql": "SELECT 1"}')
        service = SqlGenerationService(provider=provider, catalog_provider=StaticSqlCatalogProvider(_fake_catalog()))

        with pytest.raises(ValueError, match="question must not be empty"):
            service.generate("   ", user_id="u1")

    def test_provider_error_wrapped_as_sql_generation_error(self):
        """Provider errors are wrapped in SqlGenerationError with cause preserved."""
        original_error = RuntimeError("provider unavailable")
        provider = MockChatProvider(original_error)
        service = SqlGenerationService(provider=provider, catalog_provider=StaticSqlCatalogProvider(_fake_catalog()))

        with pytest.raises(SqlGenerationError) as exc_info:
            service.generate("Question", user_id="u1")

        assert exc_info.value.__cause__ is original_error
        assert "provider unavailable" not in str(exc_info.value)

    def test_user_id_passed_as_string(self):
        """User ID is converted to string for binding."""
        provider = MockChatProvider('{"sql": "SELECT 1"}')
        service = SqlGenerationService(provider=provider, catalog_provider=StaticSqlCatalogProvider(_fake_catalog()))

        service.generate("Q", user_id=123)  # int

        user_msg = provider.last_messages[1]["content"]
        assert "123" not in user_msg  # actual ID not in SQL
        assert ":user_id" in user_msg


class TestResponseParsing:
    """Tests for response parsing logic."""

    def setup_method(self):
        self.service = SqlGenerationService(
            provider=MagicMock(),
            catalog_provider=StaticSqlCatalogProvider(_fake_catalog()),
        )

    def test_parses_valid_json(self):
        """Plain JSON is parsed correctly."""
        response = '''{
            "sql": "SELECT * FROM orders",
            "referenced_tables": ["orders"],
            "referenced_columns": ["orders.id"],
            "explanation": "Test",
            "confidence": 0.85
        }'''
        result = self.service._parse_response(response)

        assert result.sql == "SELECT * FROM orders"
        assert result.referenced_tables == ("orders",)
        assert result.confidence == 0.85

    def test_parses_json_with_whitespace(self):
        """JSON with leading/trailing whitespace is handled."""
        response = '  \n  {"sql": "SELECT 1"}  \n  '
        result = self.service._parse_response(response)

        assert result.sql == "SELECT 1"

    def test_parses_json_in_markdown_fence(self):
        """JSON wrapped in ```json ... ``` is extracted."""
        response = '''```json
{
  "sql": "SELECT * FROM orders"
}
```'''
        result = self.service._parse_response(response)

        assert result.sql == "SELECT * FROM orders"

    def test_parses_json_in_generic_fence(self):
        """JSON wrapped in generic ``` ... ``` is extracted."""
        response = '''```
{
  "sql": "SELECT 1"
}
```'''
        result = self.service._parse_response(response)

        assert result.sql == "SELECT 1"

    def test_handles_missing_optional_fields(self):
        """Missing optional fields get defaults."""
        response = '{"sql": "SELECT 1"}'
        result = self.service._parse_response(response)

        assert result.referenced_tables == ()
        assert result.referenced_columns == ()
        assert result.explanation is None
        assert result.confidence is None

    def test_parses_empty_referenced_tables(self):
        """Empty referenced_tables becomes empty tuple."""
        response = '{"sql": "SELECT 1", "referenced_tables": []}'
        result = self.service._parse_response(response)

        assert result.referenced_tables == ()

    def test_raises_on_non_list_referenced_tables(self):
        """Non-list referenced_tables raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "referenced_tables": "orders"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_confidence_out_of_range(self):
        """Confidence outside 0-1 raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": 1.5}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

        response = '{"sql": "SELECT 1", "confidence": -0.1}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

        response = '{"sql": "SELECT 1", "confidence": "invalid"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_missing_sql(self):
        """Missing sql field raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="GeneratedSql contract"):
            self.service._parse_response('{"explanation": "test"}')

    def test_raises_on_empty_sql(self):
        """Empty sql field raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response('{"sql": ""}')

    def test_raises_on_whitespace_only_sql(self):
        """Whitespace-only sql raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response('{"sql": "   "}')

    def test_raises_on_missing_sql_field(self):
        """Missing sql field raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="GeneratedSql contract"):
            self.service._parse_response('{"explanation": "test"}')

    def test_raises_on_empty_response(self):
        """Empty response raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="Empty response"):
            self.service._parse_response("")

    def test_raises_on_whitespace_only(self):
        """Whitespace-only response raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="Empty response"):
            self.service._parse_response("   \n  ")

    def test_raises_on_invalid_json(self):
        """Invalid JSON raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="Provider returned invalid JSON"):
            self.service._parse_response("not json {")

    def test_raises_on_json_list_root(self):
        """JSON list root raises SqlGenerationResponseError."""
        response = '["not", "an", "object"]'
        with pytest.raises(SqlGenerationResponseError, match="must be a JSON object"):
            self.service._parse_response(response)

    def test_raises_on_json_string_root(self):
        """JSON string root raises SqlGenerationResponseError."""
        response = '"not an object"'
        with pytest.raises(SqlGenerationResponseError, match="must be a JSON object"):
            self.service._parse_response(response)

    def test_raises_on_referenced_tables_as_string(self):
        """referenced_tables as a string raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "referenced_tables": "orders"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_referenced_columns_as_string(self):
        """referenced_columns as a string raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "referenced_columns": "orders.id"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_confidence_greater_than_one(self):
        """Confidence greater than 1 raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": 1.5}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_confidence_less_than_zero(self):
        """Confidence less than 0 raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": -0.1}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_non_numeric_confidence(self):
        """Non-numeric confidence raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": "invalid"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_missing_sql(self):
        """Missing sql field raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="GeneratedSql contract"):
            self.service._parse_response('{"explanation": "test"}')

    def test_raises_on_empty_sql(self):
        """Empty sql field raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response('{"sql": ""}')

    def test_raises_on_whitespace_only_sql(self):
        """Whitespace-only sql raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response('{"sql": "   "}')

    def test_raises_on_malformed_json(self):
        """Malformed JSON raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="Provider returned invalid JSON"):
            self.service._parse_response("not json {")

    def test_raises_on_empty_response(self):
        """Empty provider response raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="Empty response"):
            self.service._parse_response("")

    def test_raises_on_whitespace_only_response(self):
        """Whitespace-only response raises SqlGenerationResponseError."""
        with pytest.raises(SqlGenerationResponseError, match="Empty response"):
            self.service._parse_response("   \n  ")

    def test_strips_code_fence_only(self):
        """Only outer code fence is stripped."""
        response = '```json\n{"sql": "SELECT 1"}\n```'
        result = self.service._parse_response(response)
        assert result.sql == "SELECT 1"

    def test_preserves_sql_inside_code_fence(self):
        """SQL content inside code fence is preserved."""
        response = '```json\n{"sql": "SELECT * FROM orders WHERE user_id = :user_id"}\n```'
        result = self.service._parse_response(response)
        assert ":user_id" in result.sql

    def test_raises_on_json_list_root(self):
        """JSON list root raises SqlGenerationResponseError."""
        response = '["not", "an", "object"]'
        with pytest.raises(SqlGenerationResponseError, match="must be a JSON object"):
            self.service._parse_response(response)

    def test_raises_on_json_string_root(self):
        """JSON string root raises SqlGenerationResponseError."""
        response = '"not an object"'
        with pytest.raises(SqlGenerationResponseError, match="must be a JSON object"):
            self.service._parse_response(response)

    def test_raises_on_confidence_greater_than_one(self):
        """Confidence greater than 1 raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": 1.5}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_confidence_less_than_zero(self):
        """Confidence less than 0 raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": -0.1}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_non_numeric_confidence(self):
        """Non-numeric confidence raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "confidence": "invalid"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)

    def test_raises_on_referenced_columns_as_string(self):
        """referenced_columns as a string raises SqlGenerationResponseError."""
        response = '{"sql": "SELECT 1", "referenced_columns": "orders.id"}'
        with pytest.raises(SqlGenerationResponseError):
            self.service._parse_response(response)


class TestServiceIntegration:
    """Integration-style tests with real renderer and catalog."""

    def test_generate_uses_catalog_provider_and_renderer(self):
        """Service uses injected catalog provider and renderer."""
        catalog = _fake_catalog()
        catalog_provider = StaticSqlCatalogProvider(catalog)
        renderer = SqlSchemaContextRenderer()

        provider = MockChatProvider('{"sql": "SELECT 1"}')

        service = SqlGenerationService(
            provider=provider,
            catalog_provider=catalog_provider,
            renderer=renderer,
        )

        result = service.generate("Q", user_id="u1")

        assert result.sql == "SELECT 1"
        # Verify the schema context was rendered from our catalog
        user_msg = provider.last_messages[1]["content"]
        assert "orders" in user_msg  # table from our fake catalog

    def test_default_renderer_used_when_none_provided(self):
        """SqlSchemaContextRenderer is used by default."""
        provider = MockChatProvider('{"sql": "SELECT 1"}')

        service = SqlGenerationService(
            provider=provider,
            catalog_provider=StaticSqlCatalogProvider(_fake_catalog()),
            renderer=None,  # Should use default
        )

        result = service.generate("Q", user_id="u1")
        assert result.sql == "SELECT 1"


class TestExceptions:
    """Tests for the new exception classes."""

    def test_sql_generation_error_is_runtime_error(self):
        """SqlGenerationError is a RuntimeError."""
        assert issubclass(SqlGenerationError, RuntimeError)

    def test_sql_generation_response_error_is_subclass(self):
        """SqlGenerationResponseError is a subclass of SqlGenerationError."""
        assert issubclass(SqlGenerationResponseError, SqlGenerationError)

    def test_exceptions_are_raised_and_caught(self):
        """Exceptions can be raised and caught properly."""
        with pytest.raises(SqlGenerationResponseError):
            raise SqlGenerationResponseError("parse failed")

        with pytest.raises(SqlGenerationError):
            raise SqlGenerationResponseError("parse failed")

    def test_provider_error_wrapped_preserves_cause(self):
        """Provider errors are wrapped with original exception as cause."""
        original_error = RuntimeError("provider unavailable")
        provider = MockChatProvider(original_error)
        service = SqlGenerationService(provider=provider, catalog_provider=StaticSqlCatalogProvider(_fake_catalog()))

        with pytest.raises(SqlGenerationError) as exc_info:
            service.generate("Question", user_id="u1")

        assert exc_info.value.__cause__ is original_error
        assert "provider unavailable" not in str(exc_info.value)


class TestUserIdLeak:
    """Tests to ensure actual user ID does not leak into any message content."""

    def test_user_id_does_not_leak(self):
        """Actual user ID must not appear in any message content."""
        actual_user_id = "real-secret-user-938472"
        provider = MockChatProvider('{"sql": "SELECT 1"}')
        service = SqlGenerationService(provider=provider, catalog_provider=StaticSqlCatalogProvider(_fake_catalog()))

        service.generate("Q", user_id=actual_user_id)

        all_content = "\n".join(
            message["content"]
            for message in provider.last_messages
        )

        assert actual_user_id not in all_content
        assert ":user_id" in all_content