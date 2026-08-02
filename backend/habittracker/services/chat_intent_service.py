"""Intent classification for the AI chat system.

Rule-based keyword matching — no LLM needed for this step.
Keeping classification deterministic makes it easy to test and reason about.

Evaluation order matters and is documented below. The order resolves
ambiguous messages that match multiple keyword sets.  The rule is:
more specific intents are checked first.

  1. UNSUPPORTED      — greetings, acknowledgements, too-short input
  2. BOTTLE_ACTIVITY  — hydration / water / bottle questions
  3. HABIT_SUMMARY    — habit completion / routine / streak questions
  4. NOTE_PATTERN     — "why" / pattern / trend / explanation questions
  5. SQL_ANALYTICS    — analytical / comparison / trend / aggregate questions
  6. GENERAL          — fallback for any other legitimate question

Examples of ordering behaviour:
  "Did I drink water after my morning habit?"
      → has "water" (bottle) AND "habit" (habit_summary)
      → resolves to BOTTLE_ACTIVITY because bottle is checked first

  "Why did I miss my habit today?"
      → has "habit" (habit_summary) AND "why" (note_pattern)
      → resolves to HABIT_SUMMARY because habit is checked before pattern

  "Compare my habit completion this month vs last month"
      → has "habit" (habit_summary) AND "compare" (sql_analytics)
      → resolves to SQL_ANALYTICS because it's checked before GENERAL
      → but after NOTE_PATTERN to avoid routing "why" questions to SQL
"""

import re

from habittracker.schemas.intent import ChatIntent

# ── Minimum message length ────────────────────────────────────────────────────
# Messages shorter than this are too terse to convey a real question.
# "hi!" (3 chars) → unsupported.  "help" (4 chars) → general.
_MIN_MESSAGE_LEN = 4

# ── Keyword sets ──────────────────────────────────────────────────────────────
# Each set is a tuple of substrings checked via `kw in msg`.
# Order within a set doesn't matter — any match wins for that intent.

_UNSUPPORTED_PHRASES: frozenset[str] = frozenset({
    "hello", "hi", "hey", "hiya", "howdy",
    "thanks", "thank you", "cheers",
    "bye", "goodbye", "see you",
    "ok", "okay", "yep", "nope", "yes", "no",
    "cool", "great", "nice", "awesome",
})

# Checked first — exact-count / time-based hydration questions.
_BOTTLE_KEYWORDS: tuple[str, ...] = (
    "bottle", "water", "hydrat", "drink", "drinking",
    " ml", "litre", "liter", "fluid",
)

# Checked second — structured habit / routine / streak queries.
_HABIT_KEYWORDS: tuple[str, ...] = (
    "habit", "routine", "check in", "checkin",
    "complete", "completed", "done today", "tracked", "tracking",
    "streak",
)

# Checked third — needs semantic (pgvector) search over notes.
_PATTERN_KEYWORDS: tuple[str, ...] = (
    "why", "pattern", "trend", "reason", "notice",
    "tend ", "tendency", "explain", "often", "usually",
    "always", "never", "most of the time",
)

# Checked fourth — analytical questions requiring flexible SQL (grouping, comparison, aggregation).
# Checked AFTER note_pattern so "why" questions go to semantic retrieval, not SQL.
_SQL_ANALYTICS_KEYWORDS: tuple[str, ...] = (
    "compare", "comparison", "versus", "vs", "against",
    "average", "mean", "median", "aggregate", "aggregation",
    "group by", "grouped by", "breakdown", "break down",
    "trend", "trends", "trending",
    "correlation", "correlate",
    "distribution", "distribute",
    "percentile", "quartile",
    "highest", "lowest", "most", "least", "maximum", "minimum",
    "top ", "bottom ", "rank", "ranking",
    "weekday", "weekend", "monthly", "weekly", "daily",
    "this month", "last month", "this week", "last week",
    "year over year", "month over month", "week over week",
    "change", "difference", "delta", "improvement", "decline",
    "rate", "ratio", "percentage", "proportion",
    "frequency", "count", "sum", "total",
)


# ── Classifier ────────────────────────────────────────────────────────────────

def classify_intent(message: str) -> ChatIntent:
    """Classify a user message into a ChatIntent.

    Evaluation order (first match wins):
      UNSUPPORTED → BOTTLE_ACTIVITY → HABIT_SUMMARY → NOTE_PATTERN → SQL_ANALYTICS → GENERAL

    Args:
        message: The raw user input.

    Returns:
        A ChatIntent enum member.
    """
    msg = message.lower().strip()

    # Too short to be a real question
    if len(msg) < _MIN_MESSAGE_LEN:
        return ChatIntent.UNSUPPORTED

    # Exact single-phrase greetings / acknowledgements
    if msg in _UNSUPPORTED_PHRASES:
        return ChatIntent.UNSUPPORTED

    # Multi-word message where every word is in the unsupported set
    words = set(re.split(r"\W+", msg)) - {""}
    if words and words <= _UNSUPPORTED_PHRASES:
        return ChatIntent.UNSUPPORTED

    if any(kw in msg for kw in _BOTTLE_KEYWORDS):
        return ChatIntent.BOTTLE_ACTIVITY

    if any(kw in msg for kw in _HABIT_KEYWORDS):
        return ChatIntent.HABIT_SUMMARY

    if any(kw in msg for kw in _PATTERN_KEYWORDS):
        return ChatIntent.NOTE_PATTERN

    if any(kw in msg for kw in _SQL_ANALYTICS_KEYWORDS):
        return ChatIntent.SQL_ANALYTICS

    # Fallback — do not classify as UNSUPPORTED for legitimate questions
    # that simply use unexpected wording.  The general handler uses
    # dashboard data + optional semantic search to give the best
    # available answer.
    return ChatIntent.GENERAL
