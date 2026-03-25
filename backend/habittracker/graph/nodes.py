"""LangGraph node definitions for the AI chat pipeline.

Each node is a function that receives the current ChatGraphState dict and
returns a dict of state updates.  LangGraph merges the returned dict back
into the state before passing it to the next node.

Node design rules:
  - Nodes that need a provider are created via a factory (make_*_node).
    The factory closes over the provider so the node signature stays plain
    (state -> dict) — required by LangGraph.
  - Nodes must not mutate the state dict in place; they return updates only.
  - classify_intent_node has no I/O and needs no factory.
  - gather_context_node and generate_answer_node receive their providers
    via closure at graph-build time (see builder.py).

Node call chain (happy path):
  classify_intent_node → gather_context_node → generate_answer_node

UNSUPPORTED shortcut (conditional edge in routing.py):
  classify_intent_node → generate_answer_node   (gather_context skipped)
"""

import logging

from habittracker.graph.state import ChatGraphState
from habittracker.providers.base import ChatProvider, EmbeddingProvider
from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_context_service import gather_context
from habittracker.services.chat_intent_service import classify_intent
from habittracker.services.chat_service import (
    FALLBACK_ANSWER,
    MAX_ANSWER_LEN,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


# ── Node 1: intent classification ─────────────────────────────────────────────

def classify_intent_node(state: ChatGraphState) -> dict:
    """Classify the user message into a ChatIntent.

    Reads:  state["message"]
    Writes: state["intent"] (str value of ChatIntent enum)

    No I/O — deterministic keyword matching only.
    """
    intent = classify_intent(state["message"])
    logger.debug("classify_intent_node: intent=%s", intent)
    return {"intent": str(intent)}


# ── Node 2: context gathering ─────────────────────────────────────────────────

def make_gather_context_node(embed_provider: EmbeddingProvider):
    """Factory that returns a gather_context_node closed over embed_provider.

    The returned node:
      Reads:  state["session"], state["user_id"], state["intent"],
              state["message"]
      Writes: state["evidence"], state["context_text"], state["used_notes"]

    Not called for UNSUPPORTED intent — the routing edge skips this node.
    """

    def gather_context_node(state: ChatGraphState) -> dict:
        context = gather_context(
            state["session"],
            state["user_id"],
            ChatIntent(state["intent"]),
            state["message"],
            embed_provider,
        )
        logger.debug(
            "gather_context_node: evidence_count=%d used_notes=%s",
            len(context.evidence),
            context.used_notes,
        )
        return {
            "evidence": context.evidence,
            "context_text": context.context_text,
            "used_notes": context.used_notes,
        }

    return gather_context_node


# ── Node 3: answer generation ─────────────────────────────────────────────────

def make_generate_answer_node(chat_provider: ChatProvider):
    """Factory that returns a generate_answer_node closed over chat_provider.

    The returned node:
      Reads:  state["evidence"], state["context_text"], state["message"]
      Writes: state["answer"]

    If evidence is empty — which happens for UNSUPPORTED intent or when no
    data exists for a supported intent — the LLM is never called and the
    safe fallback string is returned directly.
    """

    def generate_answer_node(state: ChatGraphState) -> dict:
        evidence = state.get("evidence") or []

        # No-evidence shortcut: never hallucinate when there is nothing to
        # ground the answer on.  Mirrors the same guard in handle_chat.
        if not evidence:
            logger.info("generate_answer_node: no evidence — returning fallback")
            return {"answer": FALLBACK_ANSWER}

        user_prompt = f"Data:\n{state['context_text']}\n\nQuestion: {state['message']}"
        answer = chat_provider.complete(SYSTEM_PROMPT, user_prompt)

        if len(answer) > MAX_ANSWER_LEN:
            answer = answer[:MAX_ANSWER_LEN]

        logger.info(
            "generate_answer_node: answer_chars=%d used_notes=%s",
            len(answer),
            state.get("used_notes", False),
        )
        return {"answer": answer}

    return generate_answer_node
