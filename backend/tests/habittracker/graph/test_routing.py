"""Tests for graph/routing.py — intent_router conditional edge.

intent_router is a pure function with no I/O, so every test is a direct
call with a state dict and an assertion on the return value.

Coverage:
  - UNSUPPORTED → "generate_answer"  (skips context gathering)
  - BOTTLE_ACTIVITY → "gather_context"
  - HABIT_SUMMARY → "gather_context"
  - NOTE_PATTERN → "gather_context"
  - GENERAL → "gather_context"
"""

import pytest

from habittracker.graph.routing import intent_router
from habittracker.schemas.intent import ChatIntent


@pytest.mark.parametrize("intent,expected", [
    (ChatIntent.UNSUPPORTED,     "generate_answer"),
    (ChatIntent.BOTTLE_ACTIVITY, "gather_context"),
    (ChatIntent.HABIT_SUMMARY,   "gather_context"),
    (ChatIntent.NOTE_PATTERN,    "gather_context"),
    (ChatIntent.GENERAL,         "gather_context"),
])
def test_intent_router(intent, expected):
    state = {"intent": str(intent)}
    assert intent_router(state) == expected


def test_intent_router_unsupported_string():
    """Verify UNSUPPORTED as a plain string also routes correctly."""
    state = {"intent": "unsupported"}
    assert intent_router(state) == "generate_answer"


def test_intent_router_bottle_string():
    """Verify bottle_activity as a plain string routes to gather_context."""
    state = {"intent": "bottle_activity"}
    assert intent_router(state) == "gather_context"
