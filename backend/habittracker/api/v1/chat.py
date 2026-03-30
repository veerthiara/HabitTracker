"""Chat API endpoint.

POST /api/v1/chat

Accepts a natural-language question about the user's habits, hydration,
or notes and returns a grounded, LLM-generated answer backed by structured
evidence.

Pipeline (LangGraph graph — phase-06-rev05):
  [START]
    → classify_intent_node    (keyword routing, no LLM)
    → [route: UNSUPPORTED → generate_answer_node directly]
    → gather_context_node     (fetch evidence; session injected via config)
    → generate_answer_node    (LLM completion or fallback)
  [END]

Guardrails enforced here (API layer):
  - ChatCompletionError  → HTTP 503 (Ollama unavailable or timed out)
  - Evidence cap + answer truncation are applied inside generate_answer_node.

thread_id:
  - Optional in ChatRequest. Server generates a UUID if omitted.
  - Always returned in ChatResponse so the client can continue the thread.
  - MemorySaver checkpointer maintains per-thread state in memory.
    Restarts clear all threads (expected for dev).

session handling:
  - SQLAlchemy Session is NOT stored in graph state (MemorySaver serialises
    state via msgpack; Session is not serialisable).
  - Session is injected via config["configurable"]["session"] and read by
    gather_context_node from the config argument.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.graph.builder import build_chat_graph
from habittracker.models.repository.session import get_session
from habittracker.providers.base import ChatCompletionError
from habittracker.providers.ollama import OllamaProvider
from habittracker.providers.ollama_chat import OllamaChatProvider
from habittracker.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ── Module-level singletons ───────────────────────────────────────────────────
# Providers and graph compiled once at import time; reused across requests.
_embed_provider = OllamaProvider()
_chat_provider = OllamaChatProvider()

from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
_graph = build_chat_graph(
    _embed_provider,
    _chat_provider,
    checkpointer=_MemorySaver(),
)


@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
    user_id=Depends(get_current_user_id),
) -> ChatResponse:
    """Answer a natural-language question grounded in the user's data.

    The request is processed by the LangGraph pipeline. The graph
    classifies the intent, gathers relevant evidence, and generates
    a grounded answer via the local LLM.

    Returns a safe fallback answer if:
      - The question is unsupported (greeting, too short, etc.)
      - There is no evidence available for the intent

    Returns HTTP 503 if Ollama is unavailable or times out.
    """
    thread_id = request.thread_id or str(uuid.uuid4())

    initial_state = {
        "user_id": user_id,
        "message": request.message,
        "thread_id": thread_id,
    }
    config = {
        "configurable": {
            "thread_id": thread_id,
            "session": session,   # injected here; not stored in state
        }
    }

    try:
        result = _graph.invoke(initial_state, config=config)
    except ChatCompletionError as exc:
        logger.error("Chat completion failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Chat service unavailable. Ensure Ollama is running with the correct model.",
        ) from exc

    return ChatResponse(
        answer=result["answer"],
        intent=result["intent"],
        used_notes=result.get("used_notes", False),
        evidence=result.get("evidence", []),
        thread_id=thread_id,
    )

