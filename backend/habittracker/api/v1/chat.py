"""Chat API endpoint.

POST /api/v1/chat

Accepts a natural-language question about the user's habits, hydration,
or notes and returns a grounded, LLM-generated answer backed by structured
evidence.

Pipeline (owned by chat_service.handle_chat):
  1. classify_intent      — keyword-based routing, no LLM
  2. gather_context       — fetch evidence from the right repositories
  3. No-evidence shortcut — skip LLM if nothing to ground the answer on
  4. Build prompt         — constrained system + user prompt
  5. LLM completion       — OllamaChatProvider → answer text
  6. Return ChatResponse  — answer + intent + evidence + used_notes flag

Guardrails enforced here (API layer):
  - ChatCompletionError  → HTTP 503 (Ollama unavailable or timed out)
  - Evidence cap + answer truncation are applied inside chat_service.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository.session import get_session
from habittracker.providers.base import ChatCompletionError
from habittracker.providers.ollama import OllamaProvider
from habittracker.providers.ollama_chat import OllamaChatProvider
from habittracker.schemas.chat import ChatRequest, ChatResponse
from habittracker.services.chat_service import handle_chat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Module-level singletons so httpx.Client connections are reused across
# requests.  Both providers are instantiated with values from config — no
# hardcoded strings here.
_embed_provider = OllamaProvider()
_chat_provider = OllamaChatProvider()


@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
    user_id=Depends(get_current_user_id),
) -> ChatResponse:
    """Answer a natural-language question grounded in the user's data.

    The system classifies the intent, gathers relevant evidence from the
    database, builds a constrained prompt, and calls a local LLM to
    generate a natural-language answer.

    Returns a safe fallback answer if:
      - The question is unsupported (greeting, too short, etc.)
      - There is no evidence available for the intent

    Returns HTTP 503 if Ollama is unavailable or times out.
    """
    try:
        return handle_chat(
            session=session,
            user_id=user_id,
            request=request,
            embed_provider=_embed_provider,
            chat_provider=_chat_provider,
        )
    except ChatCompletionError as exc:
        logger.error("Chat completion failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Chat service unavailable. Ensure Ollama is running with the correct model.",
        ) from exc
