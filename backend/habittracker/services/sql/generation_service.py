"""SQL generation service — SqlGenerationService.

SqlGenerationService translates a natural-language analytical question into
a safe, parameterised SELECT statement using a local LLM.

Design:
  - The service is injected with a ChatProvider (the LLM) and a
    SqlSchemaService (the approved schema). Both are injected at
    construction time so they are easily replaced in tests.
  - _build_system_prompt() and _extract_sql() are @staticmethod helpers
    on the class — they have no dependency on instance state.
  - All prompt construction is encapsulated here. No prompt text lives
    outside this service.
  - sql_generation_service is the module-level singleton for production.
    It is wired to the OllamaChatProvider singleton and sql_schema_service
    singleton. Callers import the instance, not the class.

What this service does:
  - Builds a system prompt from the approved SchemaContext
  - Sends the user question + system prompt to the LLM
  - Extracts the SQL from the LLM response (strips markdown fences etc.)
  - Returns a SqlGenerationResult carrying the SQL + original context

What this service does NOT do:
  - Validate the SQL semantically (that is the validator, rev-04)
  - Execute the SQL (that is SqlExecutionService)
  - Decide whether the question needs SQL (that is the LangGraph router)
"""

from __future__ import annotations

import logging
import re

from habittracker.providers.base import ChatCompletionError, ChatProvider
from habittracker.providers.ollama_chat import OllamaChatProvider
from habittracker.schemas.sql_chat import SqlGenerationRequest, SqlGenerationResult
from habittracker.services.sql.errors import SqlGenerationError
from habittracker.services.sql.schema_service import SqlSchemaService, sql_schema_service

logger = logging.getLogger(__name__)

# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are a PostgreSQL analyst. Your only job is to write a single, safe SELECT \
statement that answers the user's analytical question.

{schema}

Rules you must follow without exception:
- Output ONLY the SQL statement. No explanation, no markdown, no code fences.
- Always use :user_id as a bind parameter to filter by the authenticated user.
- Only reference tables and columns listed in the schema above.
- Only SELECT statements are allowed.
- Include a LIMIT clause unless the question explicitly asks for all rows.
- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, or REVOKE.
- If the question cannot be answered with the available schema, output exactly: \
UNSUPPORTED
"""

# Extracts SQL from a bare statement or a markdown code fence (```sql ... ``` or ``` ... ```)
_CODE_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# ── Service class ─────────────────────────────────────────────────────────────


class SqlGenerationService:
    """Translates a natural-language question into a SELECT statement via LLM.

    Both the chat provider and the schema service are injected so they can
    be replaced with mocks in unit tests without patching module globals.
    """

    def __init__(
        self,
        provider: ChatProvider,
        schema_svc: SqlSchemaService,
    ) -> None:
        self._provider = provider
        self._schema_svc = schema_svc

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_system_prompt(schema_summary: str) -> str:
        """Render the system prompt by injecting the schema summary."""
        return _SYSTEM_TEMPLATE.format(schema=schema_summary)

    @staticmethod
    def _extract_sql(raw: str) -> str:
        """Return clean SQL from the LLM response.

        Strips markdown code fences if present, then trims whitespace.
        Raises SqlGenerationError if the result is empty or UNSUPPORTED.
        """
        fence_match = _CODE_FENCE.search(raw)
        sql = fence_match.group(1).strip() if fence_match else raw.strip()

        if not sql:
            raise SqlGenerationError("LLM returned an empty response.")
        if sql.upper() == "UNSUPPORTED":
            raise SqlGenerationError(
                "LLM indicated the question cannot be answered with the available schema."
            )
        return sql

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self, request: SqlGenerationRequest) -> SqlGenerationResult:
        """Generate a SELECT statement for a natural-language analytical question.

        Args:
            request: Contains the user question and user_id.

        Returns:
            SqlGenerationResult with the generated SQL, original question,
            and user_id forwarded for downstream use.

        Raises:
            SqlGenerationError: LLM call failed, returned empty output, or
                                 signalled the question is unsupported.
        """
        system_prompt = self._build_system_prompt(self._schema_svc.get_summary())
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.question},
        ]

        logger.debug("SQL generation request: %s", request.question)

        try:
            raw = self._provider.complete(messages)
        except ChatCompletionError as exc:
            raise SqlGenerationError(f"LLM call failed: {exc}") from exc

        sql = self._extract_sql(raw)
        logger.debug("SQL generation result: %s", sql)

        return SqlGenerationResult(
            sql=sql,
            question=request.question,
            user_id=request.user_id,
        )


# ── Module-level singleton ────────────────────────────────────────────────────
# Callers import this instance, not the class.

sql_generation_service = SqlGenerationService(
    provider=OllamaChatProvider(),
    schema_svc=sql_schema_service,
)
