"""SQL parameter extractor — SqlParameterExtractor.

SqlParameterExtractor uses the LLM to extract a small, structured JSON payload
from a natural-language analytics question.  This is a much more reliable task
for a small local LLM than generating full SQL, because:
  - the output format is strict JSON with a small fixed schema
  - the model only needs to classify and pick values, not invent syntax
  - the schema context tells it exactly which tables and columns are valid

The extractor is only called for questions that matched a known SqlAnalyticsIntent.
It fills in the SqlTemplateParams so the SqlTemplateRenderer can produce correct SQL.

Design:
  - Class-based service; chatprovider injected at construction time.
  - _build_prompt() is a @staticmethod helper.
  - sql_parameter_extractor is the module-level singleton.
"""

from __future__ import annotations

import json
import logging
import re

from habittracker.providers.base import ChatCompletionError, ChatProvider
from habittracker.providers.ollama_chat import OllamaChatProvider
from habittracker.schemas.sql_template import SqlAnalyticsIntent, SqlTemplateParams
from habittracker.services.sql.errors import SqlParameterExtractionError

logger = logging.getLogger(__name__)

# Strip markdown code fences if the LLM wraps the JSON in them.
_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# Default values applied when the LLM omits a parameter.
_DEFAULTS_BY_INTENT: dict[SqlAnalyticsIntent, dict] = {
    SqlAnalyticsIntent.TOTAL_METRIC: {
        "table": "bottle_events",
        "metric_col": "volume_ml",
        "ts_col": "event_ts",
        "interval_days": 30,
    },
    SqlAnalyticsIntent.AVERAGE_PER_DAY: {
        "table": "bottle_events",
        "metric_col": "volume_ml",
        "ts_col": "event_ts",
        "interval_days": 30,
    },
    SqlAnalyticsIntent.COUNT_LOGS: {
        "table": "bottle_events",
        "metric_col": "id",
        "ts_col": "event_ts",
        "interval_days": 7,
    },
    SqlAnalyticsIntent.DAILY_TREND: {
        "table": "bottle_events",
        "metric_col": "volume_ml",
        "ts_col": "event_ts",
        "interval_days": 7,
    },
    SqlAnalyticsIntent.TOP_DAY: {
        "table": "bottle_events",
        "metric_col": "volume_ml",
        "ts_col": "event_ts",
        "interval_days": 30,
    },
    SqlAnalyticsIntent.HABIT_COMPLETION_RATE: {
        "table": "habit_logs",
        "metric_col": "id",
        "ts_col": "logged_date",
        "interval_days": 30,
    },
    SqlAnalyticsIntent.COMPARE_PERIODS: {
        "table": "bottle_events",
        "metric_col": "volume_ml",
        "ts_col": "event_ts",
        "interval_days": 14,
    },
}

_EXTRACTION_PROMPT = """\
You are a parameter extraction assistant.  A user asked an analytics question.
Your job is to extract the following parameters as JSON.

Question: {question}

Approved tables and their timestamp/date columns:
  bottle_events  → ts_col: event_ts,    metric options: volume_ml, id
  habit_logs     → ts_col: logged_date, metric options: id
  habits         → (no time column — join habit_logs for time-based queries)
  notes          → ts_col: created_at,  metric options: id

Output a single JSON object with these keys:
  "table"        — the primary table name (must be one of the approved tables above)
  "metric_col"   — column to aggregate (must belong to the chosen table)
  "ts_col"       — timestamp/date column for the time filter (must belong to the chosen table)
  "interval_days"— integer: how many days back the question refers to (default 30 if not specified)

Rules:
- Output ONLY the JSON object.  No explanation, no markdown, no code fences.
- If unsure about a value, use the default shown above.
- Never invent column names that are not listed above.
"""


class SqlParameterExtractor:
    """Extracts structured template parameters from a natural-language question."""

    def __init__(self, provider: ChatProvider) -> None:
        self._provider = provider

    @staticmethod
    def _build_prompt(question: str) -> str:
        return _EXTRACTION_PROMPT.format(question=question)

    def extract(
        self,
        question: str,
        intent: SqlAnalyticsIntent,
    ) -> SqlTemplateParams:
        """Extract SqlTemplateParams from *question* using the LLM.

        Args:
            question: The user's natural-language analytics question.
            intent:   Pre-classified SqlAnalyticsIntent (already determined by classifier).

        Returns:
            SqlTemplateParams filled with extracted (or default) values.

        Raises:
            SqlParameterExtractionError: LLM call failed or returned unparseable JSON.
        """
        messages = [
            {"role": "system", "content": self._build_prompt(question)},
            {"role": "user", "content": question},
        ]

        try:
            raw = self._provider.complete(messages)
        except ChatCompletionError as exc:
            raise SqlParameterExtractionError(f"LLM call failed: {exc}") from exc

        # Strip fences if present
        fence_match = _JSON_FENCE.search(raw)
        json_text = fence_match.group(1).strip() if fence_match else raw.strip()

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            logger.warning("Parameter extraction returned non-JSON: %r", raw)
            raise SqlParameterExtractionError(
                f"LLM returned non-JSON output: {exc}"
            ) from exc

        # Merge extracted values with intent-specific defaults (defaults fill gaps)
        defaults = _DEFAULTS_BY_INTENT.get(intent, {})
        merged = {**defaults, **{k: v for k, v in data.items() if v is not None}}

        return SqlTemplateParams(
            intent=intent,
            table=str(merged.get("table", defaults.get("table", "bottle_events"))),
            metric_col=str(merged.get("metric_col", defaults.get("metric_col", "volume_ml"))),
            ts_col=str(merged.get("ts_col", defaults.get("ts_col", "event_ts"))),
            interval_days=int(merged.get("interval_days", defaults.get("interval_days", 30))),
        )


# ── Module-level singleton ────────────────────────────────────────────────────

sql_parameter_extractor = SqlParameterExtractor(provider=OllamaChatProvider())
