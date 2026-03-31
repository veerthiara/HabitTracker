"""Chat orchestrator for the AI chat pipeline.

Pipeline (executed in handle_chat):
  1. classify_intent(message)         → ChatIntent
  2. gather_context(...)              → ChatContextResult (evidence + context_text)
  3. No-evidence shortcut             → return safe fallback (no LLM call)
  4. build_user_prompt(...)           → prompt string
  5. chat_provider.complete(sys, usr) → answer text
  6. Return ChatResponse

Design rules:
  - handle_chat owns the pipeline; individual stages stay in their own modules.
  - If evidence is empty, skip the LLM entirely — never hallucinate.
  - ChatCompletionError propagates to the API layer (converted to HTTP 503 in Rev 04).
  - Answer length is capped at _MAX_ANSWER_LEN characters before returning.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from habittracker.providers.base import ChatProvider, EmbeddingProvider
from habittracker.schemas.chat import ChatRequest, ChatResponse
from habittracker.services.chat_context_service import gather_context
from habittracker.services.chat_intent_service import classify_intent

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Returned when evidence is empty — never call the LLM with no data.
FALLBACK_ANSWER = "I don't have enough data to answer that."

# Hard cap on the LLM's response text. Local LLMs can occasionally produce
# very long outputs; truncating here keeps API responses predictable.
# 1000 chars ≈ 3-5 sentences — enough for a useful answer.
MAX_ANSWER_LEN = 1000

# System prompt that constrains the LLM to the provided data only.
# Kept as a module-level constant so the prompt builder can reference it
# in tests without going through the full pipeline.
SYSTEM_PROMPT = """\
You are a habit tracking assistant. You help users understand their habits, \
hydration, and notes.

Trust levels:
- Evidence in the current user message (labeled "Evidence (verified, from \
database/search)") is the authoritative source of factual claims. \
Answer ONLY from this evidence.
- Prior conversation turns in the message history are session context only. \
They may help interpret follow-up questions but are NOT verified data — \
do not treat them as facts unless confirmed by the evidence.

Rules:
- Do NOT invent or assume any data not listed in the evidence.
- If the evidence does not fully answer the question, say: \
"I don't have enough data to answer that."
- Keep answers concise (2-3 sentences max).
- Do not repeat the raw data back verbatim — summarize it naturally.\
"""

# ── Orchestrator ──────────────────────────────────────────────────────────────

def handle_chat(
    session: Session,
    user_id: uuid.UUID,
    request: ChatRequest,
    embed_provider: EmbeddingProvider,
    chat_provider: ChatProvider,
) -> ChatResponse:
    """Execute the full chat pipeline for a user message.

    Args:
        session:        SQLAlchemy session (read-only queries).
        user_id:        ID of the authenticated user.
        request:        Validated ChatRequest containing the user's message.
        embed_provider: Provider for computing embedding vectors (used for
                        semantic note search in NOTE_PATTERN / GENERAL flows).
        chat_provider:  Provider for LLM chat completion.

    Returns:
        ChatResponse with answer, intent, evidence, and used_notes flag.

    Raises:
        ChatCompletionError: if the LLM call fails — the API layer converts
                             this to HTTP 503 (implemented in Rev 04).
    """
    # Stage 1 — classify intent (deterministic, no I/O).
    intent = classify_intent(request.message)

    # Stage 2 — gather structured evidence based on intent.
    context = gather_context(
        session, user_id, intent, request.message, embed_provider
    )

    # Stage 3 — no-evidence shortcut: skip LLM entirely.
    # An empty evidence list means the intent was UNSUPPORTED, or no
    # relevant data exists. We have nothing grounded to feed the LLM.
    if not context.evidence:
        logger.info("No evidence for intent=%s — returning fallback", intent)
        return ChatResponse(
            answer=FALLBACK_ANSWER,
            intent=str(intent),
            used_notes=False,
            evidence=[],
        )

    # Stage 4 — build constrained prompt.
    user_prompt = _build_user_prompt(context.context_text, request.message)

    # Stage 5 — call LLM. ChatCompletionError propagates to the API layer.
    answer = chat_provider.complete(SYSTEM_PROMPT, user_prompt)

    # Truncate to prevent excessively long responses from local LLMs.
    if len(answer) > MAX_ANSWER_LEN:
        answer = answer[:MAX_ANSWER_LEN]

    logger.info(
        "Chat OK (intent=%s, used_notes=%s, answer_chars=%d)",
        intent,
        context.used_notes,
        len(answer),
    )

    return ChatResponse(
        answer=answer,
        intent=str(intent),
        used_notes=context.used_notes,
        evidence=context.evidence,
    )


def _build_user_prompt(context_text: str, message: str) -> str:
    """Format the data context and user question into a single user turn.

    The structure separates data from the question so the LLM can
    treat the data section as ground truth.
    """
    return f"Data:\n{context_text}\n\nQuestion: {message}"
