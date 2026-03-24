"""Context gathering for the AI chat pipeline.

Responsible for fetching structured evidence from existing repositories
and producing a lightweight context string for optional prompt assembly.

Design rules:
  - Semantic search (pgvector) is used ONLY for NOTE_PATTERN and GENERAL.
    Exact count / time-based queries (BOTTLE_ACTIVITY, HABIT_SUMMARY) never
    use embedding search — mixing fuzzy vector results would be incorrect.
  - embed_provider is only called for intents that actually need it.
  - For GENERAL, EmbeddingError from Ollama is caught so the handler
    can still return dashboard data without raising to the caller.
  - No prompt wording lives here — this module gathers facts and formats
    them as minimal structured text.  Prompt engineering belongs in the
    future chat_service / prompt builder (Rev 03).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from habittracker.models.repository import (
    bottle_event_repository,
    dashboard_repository,
)
from habittracker.models.repository.search_repository import search_notes
from habittracker.providers.base import EmbeddingError, EmbeddingProvider
from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.intent import ChatIntent
from habittracker.services.search_service import embed_query

# ── Constants ─────────────────────────────────────────────────────────────────
# Centralised limits that control how much data flows into the LLM context.
# Kept as module-level constants (not config) because they are coupling points
# between the context builder and the prompt builder — not user-tuneable knobs.

# Maximum characters of a note's content to include in evidence / context.
# 200 chars ≈ 1-2 sentences — enough for the LLM to reason about a note
# without blowing up the prompt window.
NOTE_SNIPPET_LEN = 200

# Max notes returned for a NOTE_PATTERN query (the user is explicitly
# asking about patterns, so we return more notes for richer analysis).
MAX_NOTES_PATTERN = 5

# Max notes returned for a GENERAL query (notes are supplementary here,
# dashboard data is the primary evidence, so we keep this lower).
MAX_NOTES_GENERAL = 3

# Cap on per-habit evidence items to prevent the evidence list from
# growing unboundedly when the user has many habits.  All habits still
# appear in context_text — only the evidence card list is capped.
MAX_HABIT_EVIDENCE = 5

# Max bottle events shown in context_text.
MAX_BOTTLE_EVENTS = 5


@dataclass
class ChatContextResult:
    """Structured output from the context gathering step.

    evidence:     Machine-readable facts — rendered as UI cards in the frontend.
    context_text: Factual summary text — fed into the LLM system prompt by the
                  prompt builder (Rev 03).  Kept factual, not conversational.
    used_notes:   Whether pgvector semantic search contributed to this result.
                  Downstream consumers (UI, LangGraph) use this as a signal
                  that the answer includes fuzzy/approximate data.
    """

    evidence: list[EvidenceItem] = field(default_factory=list)
    context_text: str = ""
    used_notes: bool = False


def gather_context(
    session: Session,
    user_id: uuid.UUID,
    intent: ChatIntent,
    message: str,
    embed_provider: EmbeddingProvider,
) -> ChatContextResult:
    """Gather structured context for the given intent.

    Dispatches to an intent-specific gatherer.  Each gatherer queries only
    the repositories relevant to that intent — no superfluous data is fetched.

    Args:
        session:        SQLAlchemy session (read-only queries).
        user_id:        ID of the authenticated user.
        intent:         ChatIntent enum member from classify_intent().
        message:        Original user message (used as embedding query text).
        embed_provider: Provider for computing embedding vectors.

    Returns:
        A ChatContextResult with evidence items, context_text, and the
        used_notes flag.
    """
    if intent is ChatIntent.BOTTLE_ACTIVITY:
        return _gather_bottle_activity(session, user_id)
    elif intent is ChatIntent.HABIT_SUMMARY:
        return _gather_habit_summary(session, user_id)
    elif intent is ChatIntent.NOTE_PATTERN:
        return _gather_note_pattern(session, user_id, message, embed_provider)
    elif intent is ChatIntent.GENERAL:
        return _gather_general(session, user_id, message, embed_provider)
    else:
        # UNSUPPORTED or any future unrecognised intent — nothing to gather.
        return ChatContextResult()


# ── Intent-specific gatherers ─────────────────────────────────────────────────
# Each function returns structured evidence + a factual context_text summary.
# No prompt wording ("You are a helpful assistant…") belongs here.


def _gather_bottle_activity(
    session: Session, user_id: uuid.UUID,
) -> ChatContextResult:
    today = datetime.now(timezone.utc).date()
    events = bottle_event_repository.get_events(session, user_id, for_date=today)

    total_ml = sum(e.volume_ml for e in events)
    pickup_count = len(events)

    evidence = [
        EvidenceItem(type="metric", label="Bottle pickups today", value=str(pickup_count)),
        EvidenceItem(type="metric", label="Total hydration today", value=f"{total_ml} ml"),
    ]

    lines = [
        f"Hydration summary for {today.isoformat()}:",
        f"  Pickups: {pickup_count}",
        f"  Total volume: {total_ml} ml",
    ]
    if events:
        lines.append("  Events (most recent first):")
        for e in events[:MAX_BOTTLE_EVENTS]:
            ts = e.event_ts.strftime("%H:%M") if e.event_ts else "?"
            lines.append(f"    - {ts} — {e.volume_ml} ml")

    return ChatContextResult(
        evidence=evidence,
        context_text="\n".join(lines),
        used_notes=False,
    )


def _gather_habit_summary(
    session: Session, user_id: uuid.UUID,
) -> ChatContextResult:
    today = datetime.now(timezone.utc).date()
    summary = dashboard_repository.get_summary(session, user_id, for_date=today)

    evidence = [
        EvidenceItem(type="metric", label="Active habits", value=str(summary.habits_total)),
        EvidenceItem(
            type="metric",
            label="Completed today",
            value=f"{summary.habits_done_today} of {summary.habits_total}",
        ),
    ]

    for hs in summary.habit_summaries[:MAX_HABIT_EVIDENCE]:
        status = "completed" if hs.done_today else "not completed"
        evidence.append(EvidenceItem(type="habit", label=hs.habit.name, value=status))

    lines = [
        f"Habit summary for {today.isoformat()}:",
        f"  Active habits: {summary.habits_total}",
        f"  Completed today: {summary.habits_done_today} of {summary.habits_total}",
        "  Per-habit status:",
    ]
    for hs in summary.habit_summaries:
        tick = "\u2713" if hs.done_today else "\u2717"
        lines.append(f"    {tick} {hs.habit.name} ({hs.habit.frequency})")

    return ChatContextResult(
        evidence=evidence,
        context_text="\n".join(lines),
        used_notes=False,
    )


def _gather_note_pattern(
    session: Session,
    user_id: uuid.UUID,
    message: str,
    embed_provider: EmbeddingProvider,
) -> ChatContextResult:
    query_vector = embed_query(embed_provider, message)
    rows = search_notes(session, user_id, query_vector, limit=MAX_NOTES_PATTERN)

    if not rows:
        return ChatContextResult()

    evidence = [
        EvidenceItem(
            type="note",
            label=str(row.id)[:8],
            value=row.content[:NOTE_SNIPPET_LEN],
        )
        for row in rows
    ]

    lines = ["Relevant notes from your journal:"]
    for row in rows:
        snippet = row.content[:NOTE_SNIPPET_LEN]
        lines.append(f'  (score {row.score:.2f}) "{snippet}"')

    return ChatContextResult(
        evidence=evidence,
        context_text="\n".join(lines),
        used_notes=True,
    )


def _gather_general(
    session: Session,
    user_id: uuid.UUID,
    message: str,
    embed_provider: EmbeddingProvider,
) -> ChatContextResult:
    today = datetime.now(timezone.utc).date()
    summary = dashboard_repository.get_summary(session, user_id, for_date=today)

    evidence = [
        EvidenceItem(type="metric", label="Active habits", value=str(summary.habits_total)),
        EvidenceItem(
            type="metric",
            label="Completed today",
            value=f"{summary.habits_done_today} of {summary.habits_total}",
        ),
        EvidenceItem(
            type="metric",
            label="Total hydration today",
            value=f"{summary.hydration_today_ml} ml",
        ),
    ]

    lines = [
        f"Today's overview ({today.isoformat()}):",
        f"  Active habits: {summary.habits_total}",
        f"  Completed today: {summary.habits_done_today} of {summary.habits_total}",
        f"  Total hydration: {summary.hydration_today_ml} ml",
    ]

    # Semantic search is supplementary for general questions. If Ollama is
    # unavailable we still return dashboard data — do not let embedding
    # failures break the structured-answer flow.
    used_notes = False
    try:
        query_vector = embed_query(embed_provider, message)
        rows = search_notes(session, user_id, query_vector, limit=MAX_NOTES_GENERAL)
        if rows:
            used_notes = True
            lines.append("\nRelevant notes:")
            for row in rows:
                snippet = row.content[:NOTE_SNIPPET_LEN]
                lines.append(f'  "{snippet}"')
                evidence.append(
                    EvidenceItem(type="note", label=str(row.id)[:8], value=snippet)
                )
    except EmbeddingError:
        # Ollama unavailable — degrade to dashboard-only rather than failing.
        pass

    return ChatContextResult(
        evidence=evidence,
        context_text="\n".join(lines),
        used_notes=used_notes,
    )
