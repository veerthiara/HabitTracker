"""SQL answer service — SqlAnswerService.

SqlAnswerService takes the result of a SQL execution and converts it into
a natural-language answer using a local LLM.

Design:
  - The service is injected with a ChatProvider so the LLM can be replaced
    in tests without patching module globals.
  - _format_rows() and _build_system_prompt() are @staticmethod helpers with
    no dependency on instance state.
  - If the result set is empty the service returns a safe fallback message
    without making an LLM call – there is no data to ground the answer on.
  - The prompt hard-constrains the LLM to only use the provided rows. It must
    not add information that is not present in the data.
  - sql_answer_service is the module-level singleton for production. Callers
    import the instance, not the class.

What this service does:
  - Formats SQL result rows into a readable text block for the prompt
  - Builds a system prompt that strictly grounds the LLM on that data
  - Calls the LLM and returns the answer text
  - Returns a safe fallback string when the result set is empty

What this service does NOT do:
  - Execute SQL (that is SqlExecutionService)
  - Build EvidenceItem objects (that is the chat context layer above)
  - Decide whether the question needs SQL (that is the LangGraph router)
"""

from __future__ import annotations

import logging

from habittracker.providers.base import ChatCompletionError, ChatProvider
from habittracker.providers.ollama_chat import OllamaChatProvider
from habittracker.schemas.sql_chat import SqlExecutionResult
from habittracker.services.sql.errors import SqlAnswerError

logger = logging.getLogger(__name__)

_EMPTY_RESULT_FALLBACK = (
    "I ran the query but found no matching records for your question."
)

_SYSTEM_TEMPLATE = """\
You are a data analyst assistant. Answer the user's question using ONLY the \
data rows provided below. Do not add any information that is not present in \
the data.

Question: {question}

Data:
{rows}

Rules:
- Base your answer solely on the data rows above.
- Be concise — one or two sentences.
- If the data is ambiguous or incomplete, say so briefly.
- Do not mention SQL, tables, columns, or technical implementation details.
"""


class SqlAnswerService:
    """Converts a SQL result set into a natural-language answer via LLM.

    The chat provider is injected at construction time so it can be replaced
    with a mock in unit tests without patching module globals.
    """

    def __init__(self, provider: ChatProvider) -> None:
        self._provider = provider

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _format_rows(result: SqlExecutionResult) -> str:
        """Format the result rows as a human-readable text block.

        Produces a header line followed by one row per line, with column
        names and values separated by pipes. This compact format fits
        well inside a prompt without wasting tokens on padding.
        """
        if not result.columns or not result.rows:
            return "(no data)"

        header = " | ".join(result.columns)
        lines = [header, "-" * len(header)]
        for row in result.rows:
            lines.append(" | ".join(str(row.get(col, "")) for col in result.columns))
        return "\n".join(lines)

    @staticmethod
    def _build_system_prompt(question: str, rows_text: str) -> str:
        """Render the system prompt with the question and formatted rows."""
        return _SYSTEM_TEMPLATE.format(question=question, rows=rows_text)

    # ── Public API ────────────────────────────────────────────────────────────

    def answer(self, question: str, execution_result: SqlExecutionResult) -> str:
        """Generate a natural-language answer grounded on the SQL result rows.

        Returns a safe fallback string when the result set is empty so the
        caller never needs to special-case the empty case.

        Raises:
            SqlAnswerError: if the LLM call fails.
        """
        if execution_result.row_count == 0:
            logger.debug("Empty result set – returning fallback answer.")
            return _EMPTY_RESULT_FALLBACK

        rows_text = self._format_rows(execution_result)
        system_prompt = self._build_system_prompt(question, rows_text)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        try:
            answer_text = self._provider.complete(messages)
        except ChatCompletionError as exc:
            raise SqlAnswerError(f"LLM call failed while generating answer: {exc}") from exc

        logger.debug("Answer generated (%d chars).", len(answer_text))
        return answer_text.strip()


# ── Module-level singleton ────────────────────────────────────────────────────

sql_answer_service = SqlAnswerService(provider=OllamaChatProvider())
