"""Graph builder for the LangGraph chat pipeline.

build_chat_graph() compiles a StateGraph from ChatGraphState with:
  - Three nodes: classify_intent, gather_context, generate_answer
  - One conditional edge (intent_router) after classify_intent
  - Linear edges: gather_context → generate_answer → END

Usage:
    graph = build_chat_graph(embed_provider, chat_provider)
    result = graph.invoke(initial_state)

The compiled graph is intended to be a module-level singleton in the
endpoint (instantiated once at app startup, reused across requests).

Checkpointer:
    Rev 02 — compiled without a checkpointer (no thread persistence).
    Rev 04 — will add MemorySaver for thread_id-scoped state persistence.
"""

from langgraph.graph import END, START, StateGraph

from habittracker.graph.nodes import (
    classify_intent_node,
    make_gather_context_node,
    make_generate_answer_node,
)
from habittracker.graph.routing import intent_router
from habittracker.graph.state import ChatGraphState
from habittracker.providers.base import ChatProvider, EmbeddingProvider


def build_chat_graph(
    embed_provider: EmbeddingProvider,
    chat_provider: ChatProvider,
):
    """Compile and return the LangGraph chat pipeline.

    Args:
        embed_provider: Provider for computing embeddings (used by
                        gather_context_node for NOTE_PATTERN / GENERAL).
        chat_provider:  Provider for LLM chat completion (used by
                        generate_answer_node).

    Returns:
        A compiled LangGraph CompiledStateGraph ready for .invoke().
    """
    graph = StateGraph(ChatGraphState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("gather_context", make_gather_context_node(embed_provider))
    graph.add_node("generate_answer", make_generate_answer_node(chat_provider))

    # ── Edges ─────────────────────────────────────────────────────────────────
    # Entry point
    graph.add_edge(START, "classify_intent")

    # Conditional branch: UNSUPPORTED skips context gathering
    graph.add_conditional_edges("classify_intent", intent_router)

    # Happy path: context → answer
    graph.add_edge("gather_context", "generate_answer")

    # Terminal edge
    graph.add_edge("generate_answer", END)

    return graph.compile()
