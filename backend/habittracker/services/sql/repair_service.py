"""SQL repair service — SqlRepairService.

SqlRepairService attempts to fix a SQL statement that failed at execution
time.  It sends the original question, the failed SQL, the DB error message,
and the approved schema to the LLM and asks for a corrected SELECT statement.

Design:
  - Only one repair attempt is made per pipeline run.  If the repaired SQL
    fails validation or execution a second time, the pipeline returns a safe
    user-facing fallback.
  - The repair prompt is deliberately minimal: failed SQL + DB error + schema.
    Adding more context (e.g. execution history) is saved for later revisions.
  - sql_repair_service is the module-level singleton wired to the production
    OllamaChatProvider and sql_schema_service.
"""

from __future__ import annotations

import logging
import re

from habittracker.providers.base import ChatCompletionError, ChatProvider
from habittracker.providers.ollama_chat import OllamaChatProvider
from habittracker.services.sql.errors import SqlRepairError
from habittracker.services.sql.schema_service import SqlSchemaService, sql_schema_service

logger = logging.getLogger(__name__)

# Strip markdown fences from repair response (same pattern as generation_service)
_CODE_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_REPAIR_TEMPLATE = """\
You are a PostgreSQL analyst.  A SQL query failed.  Your only job is to \
produce a corrected SELECT statement.

{schema}

Original question: {question}

Failed SQL:
{failed_sql}

Database error:
{db_error}

Rules you must follow without exception:
- Output ONLY the corrected SQL statement.  No explanation, no markdown, \
  no code fences.
- Fix the specific error shown above and nothing else.
- Do NOT use table aliases.  Write the full table name everywhere.
- Always include  <table>.user_id = :user_id  in the WHERE clause.
- Only SELECT statements are allowed.
- Include a LIMIT clause.
- If the question cannot be answered with the available schema, output \
  exactly: UNSUPPORTED
"""


class SqlRepairService:
    """Attempts a single LLM-based repair of a failed SQL statement.

    The provider and schema service are injected at construction time so
    they can be replaced with mocks in unit tests without patching globals.
    """

    def __init__(
        self,
        provider: ChatProvider,
        schema_svc: SqlSchemaService,
    ) -> None:
        self._provider = provider
        self._schema_svc = schema_svc

    def repair(
        self,
        question: str,
        failed_sql: str,
        db_error: str,
    ) -> str:
        """Attempt to repair *failed_sql* using the DB error as context.

        Args:
            question:   The original natural-language question.
            failed_sql: The SQL that caused the DB error.
            db_error:   The error string returned by Postgres / SQLAlchemy.

        Returns:
            Repaired SQL text (SELECT only, ready for re-validation).

        Raises:
            SqlRepairError: LLM call failed, returned empty output, or
                            signalled UNSUPPORTED.
        """
        prompt = _REPAIR_TEMPLATE.format(
            schema=self._schema_svc.get_summary(),
            question=question,
            failed_sql=failed_sql,
            db_error=db_error,
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Please provide the corrected SQL."},
        ]

        logger.warning(
            "SQL repair attempt: question=%r  db_error=%r  failed_sql=%r",
            question,
            db_error,
            failed_sql,
        )

        try:
            raw = self._provider.complete(messages)
        except ChatCompletionError as exc:
            raise SqlRepairError(f"LLM call failed during repair: {exc}") from exc

        fence_match = _CODE_FENCE.search(raw)
        sql = fence_match.group(1).strip() if fence_match else raw.strip()

        if not sql:
            raise SqlRepairError("LLM returned an empty response during repair.")
        if sql.upper() == "UNSUPPORTED":
            raise SqlRepairError(
                "LLM indicated the question cannot be answered with the available schema."
            )

        logger.warning("SQL repair result: %r", sql)
        return sql


# ── Module-level singleton ────────────────────────────────────────────────────

sql_repair_service = SqlRepairService(
    provider=OllamaChatProvider(),
    schema_svc=sql_schema_service,
)
