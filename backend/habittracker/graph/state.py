"""Chat graph state definition.

ChatGraphState is the single shared state object that flows through the
LangGraph chat pipeline.  Every node reads from and writes to this dict.

Design rules:
  - All fields are explicitly typed — no untyped dicts inside nodes.
  - Input fields (user_id, current_message, thread_id) are populated
    before graph.invoke() is called.
  - Output fields (intent, evidence, context_text, used_notes, answer)
    are populated by nodes during graph execution.
  - `clarify` is a placeholder for the future clarify-step (Phase 07).
    It is always None in Phase 06 and must not be read by any node.
  - `session` is NOT in state. MemorySaver serialises the full state via
    msgpack; SQLAlchemy Session objects are not serialisable. Session is
    instead injected via config["configurable"]["session"] and read by
    nodes that need it (currently only gather_context_node).

Conversation memory (Rev 06):
  - `messages` accumulates ConversationTurn pairs across checkpoint turns.
    Only *completed* pairs (user + assistant) are stored.  The current user
    input travels as `current_message`, not in `messages`, so there is no
    positional assumption or slicing required inside nodes.
  - The LangGraph `operator.add` reducer appends each node's returned list
    to the existing checkpoint list rather than overwriting it.
  - CONVERSATION_WINDOW (from core/config.py) caps the number of prior turns
    fed to the LLM per request; older turns stay in the checkpoint.
  - ConversationTurn (from schemas/conversation.py) is a shared TypedDict
    that is serialisable by MemorySaver and directly usable in Ollama payloads.
"""

import operator
import uuid
from typing import Annotated

from typing_extensions import TypedDict

from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.conversation import ConversationTurn  # noqa: F401 — re-exported


class ChatGraphState(TypedDict):
    """Shared state for the LangGraph chat pipeline.

    Input fields — populated by the endpoint before graph.invoke():
        user_id:          Authenticated user's UUID.
        current_message:  The user's message for this turn.
        thread_id:        Resolved thread ID — server-generated UUID if the
                          client did not provide one.

    Intermediate fields — written by classify_intent_node:
        intent:           String value of the classified ChatIntent enum member
                          (e.g. "bottle_activity", "unsupported").

    Intermediate fields — written by gather_context_node:
        evidence:         List of EvidenceItem objects for the UI.
        context_text:     Factual summary fed into the LLM prompt.
        used_notes:       True if pgvector semantic search contributed.

    Output field — written by generate_answer_node:
        answer:           Natural-language answer (or safe fallback).

    Conversation memory — appended by generate_answer_node only:
        messages:         Accumulated list of completed ConversationTurn pairs
                          (user + assistant) for this thread.  Only completed
                          turns live here; the current user message is always
                          in current_message, never pre-written to messages.
                          LangGraph operator.add reducer appends across turns.

    Scaffolding — always None in Phase 06:
        clarify:          Reserved for a future clarify step (Phase 07).
    """

    # ── Inputs ────────────────────────────────────────────────────────────────
    user_id: uuid.UUID
    current_message: str
    thread_id: str

    # ── Populated by classify_intent_node ────────────────────────────────────
    intent: str

    # ── Populated by gather_context_node ─────────────────────────────────────
    evidence: list[EvidenceItem]
    context_text: str
    used_notes: bool

    # ── Populated by generate_answer_node ────────────────────────────────────
    answer: str

    # ── Conversation memory — appended by generate_answer_node only ───────────
    # operator.add reducer: each node return that includes "messages" is
    # concatenated onto the existing list by LangGraph.
    messages: Annotated[list[ConversationTurn], operator.add]

    # ── Scaffolding — Phase 07 ────────────────────────────────────────────────
    clarify: str | None
