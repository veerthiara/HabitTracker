"""Chat graph state definition.

ChatGraphState is the single shared state object that flows through the
LangGraph chat pipeline.  Every node reads from and writes to this dict.

Design rules:
  - All fields are explicitly typed — no untyped dicts inside nodes.
  - Input fields (user_id, message, thread_id) are populated
    before graph.invoke() is called.
  - Output fields (intent, evidence, context_text, used_notes, answer)
    are populated by nodes during graph execution.
  - `clarify` is a placeholder for the future clarify-step (Phase 07).
    It is always None in Phase 06 and must not be read by any node.
  - `session` is NOT in state. MemorySaver serialises the full state via
    msgpack; SQLAlchemy Session objects are not serialisable. Session is
    instead injected via config["configurable"]["session"] and read by
    nodes that need it (currently only gather_context_node).
"""

import uuid

from typing_extensions import TypedDict

from habittracker.schemas.chat import EvidenceItem


class ChatGraphState(TypedDict):
    """Shared state for the LangGraph chat pipeline.

    Input fields — populated by the endpoint before graph.invoke():
        user_id:      Authenticated user's UUID.
        message:      Raw user message from ChatRequest.
        thread_id:    Resolved thread ID — server-generated UUID if the
                      client did not provide one.

    Intermediate fields — written by classify_intent_node:
        intent:       String value of the classified ChatIntent enum member
                      (e.g. "bottle_activity", "unsupported").

    Intermediate fields — written by gather_context_node:
        evidence:     List of EvidenceItem objects for the UI.
        context_text: Factual summary fed into the LLM prompt.
        used_notes:   True if pgvector semantic search contributed.

    Output field — written by generate_answer_node:
        answer:       Natural-language answer (or safe fallback).

    Scaffolding — always None in Phase 06:
        clarify:      Reserved for a future clarify step (Phase 07).
    """

    # ── Inputs ────────────────────────────────────────────────────────────────
    user_id:  uuid.UUID
    message:  str
    thread_id: str

    # ── Populated by classify_intent_node ────────────────────────────────────
    intent: str

    # ── Populated by gather_context_node ─────────────────────────────────────
    evidence: list[EvidenceItem]
    context_text: str
    used_notes: bool

    # ── Populated by generate_answer_node ────────────────────────────────────
    answer: str

    # ── Scaffolding — Phase 07 ────────────────────────────────────────────────
    clarify: str | None
