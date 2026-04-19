"""SQL analytics intent classifier — SqlIntentClassifier.

Classifies a natural-language analytics question into a SqlAnalyticsIntent
using keyword matching.  No LLM call is made; this is a fast pre-filter that
decides whether a fixed SQL template can answer the question.

If no template matches, the classifier returns SqlAnalyticsIntent.UNKNOWN and
the pipeline falls through to free-form LLM SQL generation.

Design:
  - All keyword sets are module-level tuples (same pattern as chat_intent_service).
  - Evaluation order matters: more-specific intents are checked first.
  - sql_intent_classifier is the module-level singleton.
"""

from __future__ import annotations

from habittracker.schemas.sql_template import SqlAnalyticsIntent

# ── Keyword sets (ordered from most specific to least specific) ───────────────

_COMPARE_KEYWORDS: tuple[str, ...] = (
    "compare", "vs ", "versus", "this week vs", "this month vs",
    "last week vs", "difference between",
)

_TOP_DAY_KEYWORDS: tuple[str, ...] = (
    "which day", "best day", "worst day", "highest day", "lowest day",
    "top day", "most in a day", "least in a day", "which date",
)

_DAILY_TREND_KEYWORDS: tuple[str, ...] = (
    "daily trend", "day by day", "per day breakdown", "by day", "each day",
    "breakdown by day", "show me each day", "trend over",
)

_HABIT_RATE_KEYWORDS: tuple[str, ...] = (
    "habit completion rate", "completion rate", "how often did i complete",
    "how many times did i complete", "habit streak rate",
)

_AVERAGE_KEYWORDS: tuple[str, ...] = (
    "average", "avg", "mean", "per day on average", "average per day",
    "average daily", "daily average",
)

_COUNT_KEYWORDS: tuple[str, ...] = (
    "how many",
    "how many times", "how many logs", "how many entries", "count of",
    "number of times", "number of logs", "total count", "how many events",
)

_TOTAL_KEYWORDS: tuple[str, ...] = (
    "total", "sum", "in total", "altogether", "combined", "how much in total",
    "how much did i drink", "how much water",
)


class SqlIntentClassifier:
    """Classifies a question into a SqlAnalyticsIntent via keyword matching."""

    def classify(self, question: str) -> SqlAnalyticsIntent:
        """Return the best-matching SqlAnalyticsIntent for *question*.

        Evaluation order (first match wins):
          COMPARE_PERIODS → TOP_DAY → DAILY_TREND → HABIT_COMPLETION_RATE
          → AVERAGE_PER_DAY → COUNT_LOGS → TOTAL_METRIC → UNKNOWN
        """
        msg = question.lower()

        if any(kw in msg for kw in _COMPARE_KEYWORDS):
            return SqlAnalyticsIntent.COMPARE_PERIODS

        if any(kw in msg for kw in _TOP_DAY_KEYWORDS):
            return SqlAnalyticsIntent.TOP_DAY

        if any(kw in msg for kw in _DAILY_TREND_KEYWORDS):
            return SqlAnalyticsIntent.DAILY_TREND

        if any(kw in msg for kw in _HABIT_RATE_KEYWORDS):
            return SqlAnalyticsIntent.HABIT_COMPLETION_RATE

        if any(kw in msg for kw in _AVERAGE_KEYWORDS):
            return SqlAnalyticsIntent.AVERAGE_PER_DAY

        if any(kw in msg for kw in _COUNT_KEYWORDS):
            return SqlAnalyticsIntent.COUNT_LOGS

        if any(kw in msg for kw in _TOTAL_KEYWORDS):
            return SqlAnalyticsIntent.TOTAL_METRIC

        return SqlAnalyticsIntent.UNKNOWN


# ── Module-level singleton ────────────────────────────────────────────────────

sql_intent_classifier = SqlIntentClassifier()
