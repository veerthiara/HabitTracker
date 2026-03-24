"""Shared intent type for the AI chat pipeline.

ChatIntent is the single source of truth for all valid intent values.
Both the classifier (chat_intent_service) and context builder
(chat_context_service) import from here, avoiding circular
dependencies and duplicated string literals.

Using StrEnum so that:
  - Values are valid strings (JSON-serialisable, usable in Pydantic models).
  - Typos are caught at import time, not at runtime string comparison.
  - IDE autocompletion and exhaustiveness checks work out of the box.
"""

from enum import StrEnum


class ChatIntent(StrEnum):
    """Classified intent of a user chat message.

    Evaluation order in classify_intent() is:
      UNSUPPORTED → BOTTLE_ACTIVITY → HABIT_SUMMARY → NOTE_PATTERN → GENERAL

    GENERAL is the fallback — any legitimate question that doesn't match
    a more specific intent still gets the best available answer.
    UNSUPPORTED is reserved for non-questions (greetings, acknowledgements).
    """

    HABIT_SUMMARY = "habit_summary"
    BOTTLE_ACTIVITY = "bottle_activity"
    NOTE_PATTERN = "note_pattern_question"
    GENERAL = "general_question"
    UNSUPPORTED = "unsupported"
