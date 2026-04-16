"""Conditional edge routing for the LangGraph chat pipeline.

The intent_router function is used as the condition function on the
conditional edge that follows classify_intent_node.  It inspects the
classified intent and returns the name of the next node to execute.

Routing table:
  UNSUPPORTED   → "generate_answer"   (skip context — return fallback)
  SQL_ANALYTICS → "sql_analytics"     (skip context — SQL pipeline handles everything)
  All others    → "gather_context"    (fetch evidence, then generate)

Keeping routing in its own module:
  - makes the branching logic trivially testable (pure function, no I/O)
  - keeps nodes.py free of routing decisions
  - mirrors the principle that routing is structural, not buried in a
    conditional inside a service function
"""

from habittracker.graph.state import ChatGraphState
from habittracker.schemas.intent import ChatIntent


def intent_router(state: ChatGraphState) -> str:
    """Return the name of the next node based on the classified intent.

    Called by LangGraph on the conditional edge after classify_intent_node.

    Args:
        state: Current graph state with "intent" populated.

    Returns:
        "generate_answer" for UNSUPPORTED intent (skips context gathering).
        "sql_analytics"   for SQL_ANALYTICS intent (SQL pipeline handles answer).
        "gather_context"  for all other intents.
    """
    if state["intent"] == ChatIntent.UNSUPPORTED:
        return "generate_answer"
    if state["intent"] == ChatIntent.SQL_ANALYTICS:
        return "sql_analytics"
    return "gather_context"
