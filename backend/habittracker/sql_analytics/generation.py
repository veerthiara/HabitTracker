"""SQL Generation Service.

Reusable service that converts natural-language questions into structured SQL candidates.
"""

import json
import re

from pydantic import ValidationError

from habittracker.providers.base import ChatProvider
from habittracker.sql_analytics.catalog import SqlCatalogProvider
from habittracker.sql_analytics.contracts import GeneratedSql, SqlGenerationRequest
from habittracker.sql_analytics.renderer import SqlSchemaContextRenderer
from habittracker.sql_analytics.prompts import build_sql_generation_messages


class SqlGenerationError(RuntimeError):
    """Base error raised when SQL candidate generation fails."""


class SqlGenerationResponseError(SqlGenerationError):
    """Raised when a provider response cannot be parsed into GeneratedSql."""


class SqlGenerationService:
    """Generates SQL from natural-language questions using a chat provider."""

    def __init__(
        self,
        provider: ChatProvider,
        catalog_provider: SqlCatalogProvider,
        renderer: "SqlSchemaContextRenderer | None" = None,
    ) -> None:
        self._provider = provider
        self._catalog_provider = catalog_provider
        self._renderer = renderer or SqlSchemaContextRenderer()

    def generate(
        self,
        question: str,
        user_id: str | int,
        conversation_history: tuple[dict[str, str], ...] = (),
    ) -> GeneratedSql:
        """Generate SQL from a natural-language question.

        Args:
            question: The user's analytical question.
            user_id: The authenticated user ID (passed as bound parameter :user_id).
            conversation_history: Optional prior conversation turns.

        Returns:
            GeneratedSql with the SQL and metadata.

        Raises:
            ValueError: If the question is empty.
            SqlGenerationError: If the provider fails to respond.
            SqlGenerationResponseError: If the response cannot be parsed into GeneratedSql.
        """
        if not question or not question.strip():
            raise ValueError("question must not be empty")

        catalog = self._catalog_provider.get_catalog()
        schema_context = self._renderer.render(catalog)

        request = SqlGenerationRequest(
            question=question.strip(),
            user_id=str(user_id),
            schema_context=schema_context,
            conversation_history=conversation_history,
        )

        messages = build_sql_generation_messages(request)
        try:
            response_text = self._provider.complete(list(messages))
        except Exception as exc:
            raise SqlGenerationError("SQL generation provider call failed") from exc

        return self._parse_response(response_text)

    def _parse_response(self, response_text: str) -> GeneratedSql:
        """Parse provider response into GeneratedSql.

        Handles:
        - Plain JSON
        - JSON with surrounding whitespace
        - JSON inside markdown code fences
        - Missing/invalid fields
        - Invalid confidence values (raises)

        Raises:
            SqlGenerationResponseError: If the response cannot be parsed into GeneratedSql.
        """
        if not response_text or not response_text.strip():
            raise SqlGenerationResponseError("Empty response from provider")

        text = response_text.strip()
        text = self._strip_code_fence(text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SqlGenerationResponseError("Provider returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise SqlGenerationResponseError("Provider response must be a JSON object")

        try:
            return GeneratedSql.model_validate(data)
        except ValidationError as exc:
            raise SqlGenerationResponseError("Provider response does not match the GeneratedSql contract") from exc

    def _strip_code_fence(self, text: str) -> str:
        """Remove outer markdown code fence if present."""
        pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
        match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text