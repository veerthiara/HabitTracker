# Phase 05 Rev 02 — Intent Classification + Context Gathering

## Goal

Implement the first two pipeline stages of the AI chat system:

1. **Intent classification** — deterministic keyword-based routing of user messages to one of five intent types.
2. **Context gathering** — intent-aware evidence collection from existing repositories, formatted for both UI display and LLM prompt injection.

After initial implementation, the code was refactored for cleaner boundaries, type safety, and future extensibility without adding LangGraph or thread memory.

## Key Decisions

- **`ChatIntent` StrEnum in `schemas/intent.py`.** Replaces raw `INTENT_*` string constants. StrEnum gives typo-catching at import time, IDE autocompletion, and exhaustiveness checking while remaining JSON-serialisable (since `StrEnum` values are also plain strings). Placed in `schemas/` because it is a shared type used by both the classifier and context service — avoids circular import between services.
- **Rename `chat_data_service.py` → `chat_context_service.py`.** The module builds evidence + prompt context, not raw data. The new name better reflects its role as a context builder that sits between the classifier and the future prompt builder. `ChatDataResult` → `ChatContextResult` for consistency.
- **Rule-based intent classification, no LLM.** Keyword matching is deterministic, instantaneous, and requires no external call. For structured queries (habit counts, hydration stats, note patterns), keyword routing is sufficient and produces easily testable behaviour.
- **Evaluation order as a design contract.** Keywords are checked in an explicit order: `BOTTLE_ACTIVITY` before `HABIT_SUMMARY` before `NOTE_PATTERN`. Order is documented in the module docstring, tested with explicit ordering tests, and explained with inline examples showing ambiguous-message resolution.
- **Fallback is `GENERAL`, never `UNSUPPORTED`.** A message that doesn't match any keyword set still deserves the best available answer (dashboard overview + optional semantic search). `UNSUPPORTED` is reserved for inputs with no semantic content.
- **Semantic search only where appropriate.** `BOTTLE_ACTIVITY` and `HABIT_SUMMARY` are count/time-based queries — mixing pgvector cosine similarity results into them would be incorrect. Only `NOTE_PATTERN` and `GENERAL` use embeddings.
- **`EmbeddingError` caught in `_gather_general` only.** For `NOTE_PATTERN`, if Ollama is unavailable there is nothing to return — the error bubbles. For `GENERAL`, dashboard data is enough, so degrading gracefully is correct.
- **Constants centralised as module-level with comments.** `NOTE_SNIPPET_LEN`, `MAX_NOTES_PATTERN`, `MAX_NOTES_GENERAL`, `MAX_HABIT_EVIDENCE`, `MAX_BOTTLE_EVENTS` are coupling points between the context builder and the future prompt builder — not user-tuneable knobs. Kept as named constants with rationale comments rather than pushed to config.
- **No new SQL.** The context service composes entirely from existing repository functions.
- **Unused imports removed.** `habit_log_repository` and `habit_repository` were imported but not used — removed. `dashboard_repository` already aggregates all needed habit/log data.

## Architectural Context

This revision implements pipeline stages 1 and 2 of the chat flow:

```
User message
    │
    ▼
[1] classify_intent()          ← chat_intent_service.py  (this revision)
    │ returns ChatIntent enum
    ▼
[2] gather_context()           ← chat_context_service.py  (this revision)
    │ evidence: list[EvidenceItem]
    │ context_text: str  (injected into LLM system prompt)
    │ used_notes: bool
    ▼
[3] build_prompt()             ← Rev 03 (not yet implemented)
    ▼
[4] OllamaChatProvider.chat()  ← Rev 01 (existing)
    ▼
ChatResponse → API → UI
```

Type flow: `str` → `ChatIntent` (StrEnum) → `ChatContextResult` → (Rev 03) `ChatResponse`.

## Flow

```
classify_intent(message) → ChatIntent
  ├── len < 4 or greeting            → UNSUPPORTED
  ├── bottle/water/hydrat/drink/ml   → BOTTLE_ACTIVITY
  ├── habit/routine/tracked/streak   → HABIT_SUMMARY
  ├── why/pattern/trend/often        → NOTE_PATTERN
  └── (no match)                     → GENERAL

gather_context(session, user_id, intent, message, embed_provider) → ChatContextResult
  ├── BOTTLE_ACTIVITY   → bottle_event_repository.get_events(today)
  ├── HABIT_SUMMARY     → dashboard_repository.get_summary(today)
  ├── NOTE_PATTERN      → embed_query() → search_notes(limit=5)
  ├── GENERAL           → dashboard_repository.get_summary()
  │                       + embed_query() → search_notes(limit=3)
  │                       (EmbeddingError → degrade to dashboard only)
  └── UNSUPPORTED       → ChatContextResult() (empty)
```

## Scope Implemented

- `ChatIntent` StrEnum (`schemas/intent.py`) with 5 members
- `classify_intent(message: str) → ChatIntent` — keyword-based, ordered evaluation
- `ChatContextResult` dataclass with `evidence`, `context_text`, `used_notes`
- `gather_context(session, user_id, intent, message, embed_provider) → ChatContextResult`
- 4 private gatherers: `_gather_bottle_activity`, `_gather_habit_summary`, `_gather_note_pattern`, `_gather_general`
- Centralised constants: `NOTE_SNIPPET_LEN`, `MAX_NOTES_PATTERN`, `MAX_NOTES_GENERAL`, `MAX_HABIT_EVIDENCE`, `MAX_BOTTLE_EVENTS`
- Tests for intent classifier — pure function, zero mocks + enum type tests
- Tests for context service — stacked `@patch` decorators, including graceful degradation on `EmbeddingError`
- Total test count: 113

## Files Changed

- `backend/habittracker/schemas/intent.py` — new (ChatIntent StrEnum)
- `backend/habittracker/services/chat_intent_service.py` — rewritten (uses ChatIntent enum, `_MIN_MESSAGE_LEN` constant, improved docstring with evaluation order examples)
- `backend/habittracker/services/chat_context_service.py` — new (renamed from `chat_data_service.py`, uses ChatIntent enum, `ChatContextResult`, removed unused repo imports)
- `backend/habittracker/services/chat_data_service.py` — deleted (replaced by `chat_context_service.py`)
- `backend/tests/habittracker/services/test_chat_intent_service.py` — rewritten (uses ChatIntent enum, added `TestClassifyIntentReturnType` class)
- `backend/tests/habittracker/services/test_chat_context_service.py` — new (renamed from `test_chat_data_service.py`, uses ChatIntent enum, `ChatContextResult`, updated patch paths)
- `backend/tests/habittracker/services/test_chat_data_service.py` — deleted
- `docs/implementation/phase-05-rev02.md` — this file

## Notes

- `ChatIntent` is a `StrEnum` so its values work directly in Pydantic models (`ChatResponse.intent: str`). No serialiser changes needed.
- The `_MIN_MESSAGE_LEN = 4` constant in the classifier replaces a bare `4` magic number.
- The ordering tests and docstring examples explicitly document how ambiguous messages (containing keywords from multiple intents) are resolved — this was implicit before.
- Constants like `MAX_NOTES_PATTERN` are now public (no underscore prefix) so the future prompt builder can reference them if needed, without re-defining the same numbers.

## Next Step

Rev 03 — Prompt builder + chat endpoint:
- `habittracker/services/chat_service.py` — `build_system_prompt(result: ChatContextResult) → str` + `handle_chat(session, user_id, request) → ChatResponse`
- `habittracker/api/v1/chat.py` — POST `/api/v1/chat` endpoint
- Wire `OllamaChatProvider` from Rev 01 with intent + context from Rev 02
