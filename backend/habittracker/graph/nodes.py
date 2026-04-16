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

Conversation memory design (Rev 06):
  - state["messages"] holds only *completed* user+assistant pairs.
    The current user input always lives in state["current_message"] and is
    never pre-written to messages — this eliminates any positional slicing trick.
  - generate_answer_node is the sole writer of messages.  It appends both the
    user turn (current_message) and the assistant turn (answer) together at the
    end of the node, keeping messages always in a consistent even-length state.
  - classify_intent_node does NOT touch messages.
  - CONVERSATION_WINDOW (from core/config.py) controls how many prior turns
    are included in the LLM payload.  Older turns stay in the checkpoint.

Prompt structure (three explicit layers):
  1. [system]  — identity + trust rules
  2. [user/assistant]  — windowed prior completed turns (verbatim)
  3. [user]  — current turn: verified DB evidence + the user's question

    Trust is communicated via the system prompt (layer 1), not by embedding
    labels inside the user message content.

Node call chain (happy path):
  classify_intent_node → gather_context_node → generate_answer_node

UNSUPPORTED shortcut (conditional edge in routing.py):
  classify_intent_node → generate_answer_node   (gather_context skipped)
"""

import logging

from habittracker.core.config import CONVERSATION_WINDOW
from habittracker.graph.state import ChatGraphState
from habittracker.providers.base import ChatProvider, EmbeddingProvider
from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.conversation import ConversationTurn
from habittracker.schemas.intent import ChatIntent
from habittracker.schemas.sql_chat import SqlGenerationRequest
from habittracker.services.chat_context_service import gather_context
from habittracker.services.chat_intent_service import classify_intent
from habittracker.services.chat_service import (
    FALLBACK_ANSWER,
    MAX_ANSWER_LEN,
    SYSTEM_PROMPT,
)
from habittracker.services.sql.pipeline_service import SqlPipelineService, sql_pipeline_service

logger = logging.getLogger(__name__)


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_user_content(
    context_text: str,
    current_message: str,
) -> str:
    """Build the content string for the current user turn in the LLM payload.

    Contains only the two things unique to this turn:
      1. Verified evidence from DB/search — explicitly labeled so the model
         knows it is the authoritative source of factual claims.
      2. The user's question.

    Prior conversation turns are NOT included here — they are already present
    as structured role/content messages earlier in the payload (layer 2 in
    _build_llm_payload).  Duplicating them as a text recap would be redundant
    and could confuse the model about trust levels.
    """
    return (
        f"Evidence (verified, from database/search):\n{context_text}"
        f"\n\nQuestion: {current_message}"
    )


def _build_llm_payload(
    system_prompt: str,
    history: list[ConversationTurn],
    context_text: str,
    current_message: str,
) -> list[ConversationTurn]:
    """Assemble the ordered message list sent to the chat provider.

    Layer 1 — system (role="system"):
        Identity + trust rules. Always first. Never repeated.

    Layer 2 — prior completed turns (role="user" / role="assistant"):
        Windowed pairs from state["messages"]. Sent verbatim as structured
        messages so the model has natural conversational context.
        These are labeled in the system prompt as session history, not
        verified DB evidence.

    Layer 3 — current user turn (role="user"):
        Verified DB/search evidence + the user's question for this turn.
        History is NOT repeated here — it is already present in layer 2.

    Returns list[ConversationTurn] passable directly to ChatProvider.complete().
    """
    payload: list[ConversationTurn] = [
        ConversationTurn(role="system", content=system_prompt)
    ]
    payload.extend(history)
    payload.append(
        ConversationTurn(
            role="user",
            content=_build_user_content(context_text, current_message),
        )
    )
    return payload


# ── Node 1: intent classification ─────────────────────────────────────────────

def classify_intent_node(state: ChatGraphState) -> dict:
    """Classify the user message into a ChatIntent.

    Reads:  state["current_message"]
    Writes: state["intent"] (str value of ChatIntent enum)

    No I/O — deterministic keyword matching only.
    Does NOT touch state["messages"]; generate_answer_node is the sole
    writer of conversation history.
    """
    intent = classify_intent(state["current_message"])
    logger.info("classify_intent_node: intent=%s", intent)
    return {"intent": str(intent)}


# ── Node 2: context gathering ─────────────────────────────────────────────────

def make_gather_context_node(embed_provider: EmbeddingProvider):
    """Factory that returns a gather_context_node closed over embed_provider.

    The returned node:
      Reads:  state["user_id"], state["intent"], state["current_message"]
              config["configurable"]["session"]  ← injected; not in state
      Writes: state["evidence"], state["context_text"], state["used_notes"]

    Session is in config rather than state because MemorySaver serialises
    the full state via msgpack and SQLAlchemy Sessions are not serialisable.
    LangGraph passes config as the optional second argument to any node
    whose function signature accepts it.

    Not called for UNSUPPORTED intent — the routing edge skips this node.
    """

    def gather_context_node(state: ChatGraphState, config) -> dict:
        session = (config or {}).get("configurable", {}).get("session")
        context = gather_context(
            session,
            state["user_id"],
            ChatIntent(state["intent"]),
            state["current_message"],
            embed_provider,
        )
        logger.info(
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
      Reads:  state["current_message"], state["evidence"],
              state["context_text"], state["messages"]
      Writes: state["answer"]
               state["messages"] — appends [user_turn, assistant_turn] together

    messages is the sole responsibility of this node.  After the answer is
    produced, both the current user turn and the assistant answer are appended
    as a completed pair.  This keeps messages always in an even-length,
    consistent state — no positional assumptions are needed anywhere.

    If evidence is empty the LLM is never called.  The fallback answer is
    still recorded in messages so the thread history remains complete.
    """

    def generate_answer_node(state: ChatGraphState) -> dict:
        current_message = state["current_message"]
        evidence = state.get("evidence") or []

        # No-evidence shortcut — never hallucinate without grounded data.
        if not evidence:
            logger.info("generate_answer_node: no evidence — returning fallback")
            return {
                "answer": FALLBACK_ANSWER,
                "messages": [
                    ConversationTurn(role="user", content=current_message),
                    ConversationTurn(role="assistant", content=FALLBACK_ANSWER),
                ],
            }

        # Apply the sliding window to prior completed turns.
        prior_turns: list[ConversationTurn] = state.get("messages") or []
        windowed = prior_turns[-CONVERSATION_WINDOW:]

        payload = _build_llm_payload(
            system_prompt=SYSTEM_PROMPT,
            history=windowed,
            context_text=state["context_text"],
            current_message=current_message,
        )

        answer = chat_provider.complete(payload)

        if len(answer) > MAX_ANSWER_LEN:
            answer = answer[:MAX_ANSWER_LEN]

        logger.info(
            "generate_answer_node: answer_chars=%d used_notes=%s",
            len(answer),
            state.get("used_notes", False),
        )
        return {
            "answer": answer,
            "messages": [
                ConversationTurn(role="user", content=current_message),
                ConversationTurn(role="assistant", content=answer),
            ],
        }

    return generate_answer_node


# ── Node 4: SQL analytics ─────────────────────────────────────────────────────

def make_sql_analytics_node(pipeline_svc: SqlPipelineService):
    """Factory that returns a sql_analytics_node closed over pipeline_svc.

    The returned node:
      Reads:  state["user_id"], state["current_message"]
              config["configurable"]["session"]  ← injected; not in state
      Writes: state["answer"], state["evidence"], state["context_text"],
              state["used_notes"], state["sql_pipeline_result"],
              state["messages"]

    The node runs the full SQL pipeline (generation → validation →
    execution → answer) and writes its output directly to the state fields
    that generate_answer_node would normally populate.  This means the
    SQL analytics path terminates at this node — generate_answer_node is
    NOT called (the edge goes sql_analytics → END).

    On pipeline failure, a safe fallback answer is returned and success=False
    is recorded in sql_pipeline_result.  The node never raises.
    """

    def sql_analytics_node(state: ChatGraphState, config) -> dict:
        session = (config or {}).get("configurable", {}).get("session")
        current_message = state["current_message"]
        user_id = state["user_id"]

        request = SqlGenerationRequest(
            question=current_message,
            user_id=str(user_id),
        )
        result = pipeline_svc.run(request, session)

        if result.success and result.answer:
            answer = result.answer
            # Build evidence items from execution result rows (up to 5 rows).
            evidence: list[EvidenceItem] = []
            if result.execution:
                for row in result.execution.rows[:5]:
                    label = " | ".join(str(v) for v in row.values())
                    evidence.append(
                        EvidenceItem(type="sql_result", label=label, value=label)
                    )
        else:
            answer = result.failure_reason or FALLBACK_ANSWER
            evidence = []

        logger.info(
            "sql_analytics_node: success=%s answer_chars=%d evidence_count=%d",
            result.success,
            len(answer),
            len(evidence),
        )

        return {
            "answer": answer,
            "evidence": evidence,
            "context_text": "",
            "used_notes": False,
            "sql_pipeline_result": result,
            "messages": [
                ConversationTurn(role="user", content=current_message),
                ConversationTurn(role="assistant", content=answer),
            ],
        }

    return sql_analytics_node
