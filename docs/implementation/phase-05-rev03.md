# Phase 05 Rev 03 — Chat Orchestrator (Prompt Building + LLM Answer Generation)

## Goal

Implement `chat_service.py` — the orchestrator that wires together the pipeline stages from Rev 01 and Rev 02 into a complete end-to-end chat flow, from user message to LLM-generated natural-language answer.

## Key Decisions

- **`handle_chat` owns the pipeline; stages remain in their own modules.** `classify_intent` and `gather_context` are imported as functions and called sequentially — not inlined. This keeps each module independently testable and replaceable.
- **No-evidence shortcut — skip the LLM if evidence is empty.** An empty evidence list means the intent was UNSUPPORTED or no relevant data exists. There is nothing grounded to feed the LLM, so returning the safe fallback immediately is both correct and efficient (no Ollama round-trip). Rule: never call the LLM with no data.
- **`ChatCompletionError` propagates, not caught here.** The orchestrator's job is assembly, not error handling. The API layer (Rev 04) converts Ollama failures to HTTP 503. Catching errors here would obscure them from the caller.
- **Answer length capped at `MAX_ANSWER_LEN = 1000` chars.** Local LLMs can occasionally produce unexpectedly long outputs. Capping at the service layer keeps API responses predictable regardless of which model is running. 1000 chars ≈ 3–5 sentences — enough for a useful answer.
- **`SYSTEM_PROMPT` and `MAX_ANSWER_LEN` are public module constants.** They are referenced in tests directly, avoiding magic string/number duplication between tests and production code. If they change, tests automatically reflect the change.
- **Prompt structure: data block + question.** The `_build_user_prompt` helper formats the context_text from Rev 02 as a `"Data:\n...\n\nQuestion: ..."` block. This structure makes the separation between ground truth and question unambiguous to the LLM.
- **Providers are injectable parameters, not module-level singletons.** `embed_provider` and `chat_provider` are passed into `handle_chat`. The API endpoint (Rev 04) will create and hold the singleton instances. This makes unit tests trivial — pass a MagicMock, no patching needed.

## Architectural Context

Rev 03 completes the internal pipeline:

```
User message
    │
    ▼
[1] classify_intent()         → ChatIntent        (Rev 02 — chat_intent_service)
    │
    ▼
[2] gather_context()          → ChatContextResult  (Rev 02 — chat_context_service)
    │ evidence: list[EvidenceItem]       ← if empty → return FALLBACK_ANSWER
    │ context_text: str
    │ used_notes: bool
    ▼
[3] _build_user_prompt()      → str               (Rev 03 — chat_service)
    │
    ▼
[4] chat_provider.complete()  → answer: str       (Rev 01 — OllamaChatProvider)
    │ truncate to MAX_ANSWER_LEN
    ▼
[5] ChatResponse               →                  (Rev 04 — API endpoint)
```

The next revision (Rev 04) wraps `handle_chat` in the FastAPI endpoint, adds the HTTP 503 guardrail, and wires the router.

## Flow

```
handle_chat(session, user_id, request, embed_provider, chat_provider)
  ├── classify_intent(request.message)       → ChatIntent
  ├── gather_context(session, user_id, ...)  → ChatContextResult
  ├── context.evidence == [] ?
  │     └── return ChatResponse(answer=FALLBACK_ANSWER, evidence=[])
  ├── _build_user_prompt(context_text, message)
  ├── chat_provider.complete(SYSTEM_PROMPT, user_prompt)
  │     (ChatCompletionError propagates)
  ├── truncate answer to MAX_ANSWER_LEN
  └── return ChatResponse(answer, intent, used_notes, evidence)
```

## Scope Implemented

- `handle_chat(session, user_id, request, embed_provider, chat_provider) → ChatResponse`
- `_build_user_prompt(context_text, message) → str`
- `SYSTEM_PROMPT` — constrained system prompt (data-only, 2-3 sentences max)
- `FALLBACK_ANSWER = "I don't have enough data to answer that."`
- `MAX_ANSWER_LEN = 1000`
- Tests: 17 new tests covering happy path, no-evidence shortcut, answer truncation, error propagation
- Total test count: 130 (up from 113 in Rev 02)

## Files Changed

- `backend/habittracker/services/chat_service.py` — new
- `backend/tests/habittracker/services/test_chat_service.py` — new
- `docs/implementation/phase-05-rev03.md` — this file

## Notes

- `_build_user_prompt` is a private helper but imported directly in tests to verify its behaviour in isolation. This is intentional — the prompt format is a contract between the service and the LLM.
- The system prompt does not include today's date or user name — these would require additional context injection. If needed, this can be added without changing the pipeline structure.

## Next Step

Rev 04 — Chat endpoint + guardrails:
- `habittracker/api/v1/chat.py` — `POST /api/v1/chat`, module-level provider singletons, HTTP 503 on `ChatCompletionError`
- `habittracker/server.py` — register chat router
- Tests: API-layer tests with mocked `handle_chat`
