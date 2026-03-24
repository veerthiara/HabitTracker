# Phase 05 Rev 04 — Chat Endpoint + Guardrails

## Goal

Expose the full chat pipeline from Rev 01–03 as a working HTTP endpoint: `POST /api/v1/chat`. Add the HTTP guardrail that converts `ChatCompletionError` to HTTP 503, and register the router.

## Key Decisions

- **Endpoint owns the HTTP layer only.** `handle_chat` is called as a single function call — no pipeline logic inside the endpoint. This keeps the endpoint thin and all business logic testable without HTTP.
- **Module-level provider singletons.** `_embed_provider` and `_chat_provider` are instantiated once at module load, not per-request. This reuses `httpx.Client` connections across requests, matching the pattern in `search.py`. They are not injected as FastAPI dependencies — the endpoint is the natural owner.
- **`ChatCompletionError` → HTTP 503 here, not in `chat_service`.** The service layer propagates the error; the API layer converts it to HTTP with a user-facing message. This keeps the service layers free of HTTP concerns and the 503 logic colocated with the endpoint.
- **`raise_server_exceptions=False` in TestClient.** Needed so 503 responses are inspectable as HTTP responses rather than having pytest re-raise the exception. The guardrail test verifies the HTTP status, not the Python exception.
- **Test hierarchy mirrors app hierarchy.** Tests placed at `tests/habittracker/api/v1/` — consistent with `tests/habittracker/services/` and `tests/habittracker/providers/`.
- **`handle_chat` patched at `habittracker.api.v1.chat.handle_chat`.** The endpoint imports and calls `handle_chat` — patching at the import site in the endpoint module is the correct approach.
- **Dependency overrides for session + user ID.** `get_session` and `get_current_user_id` are overridden on the test app so no real DB or auth is needed in endpoint tests. Business logic is tested separately.

## Architectural Context

Rev 04 completes the Phase 05 pipeline:

```
POST /api/v1/chat
    │
    ▼
chat() — api/v1/chat.py                 ← this revision
    │ Depends: get_session, get_current_user_id
    │
    ▼
handle_chat()                           ← Rev 03 — chat_service.py
    ├── classify_intent()               ← Rev 02 — chat_intent_service.py
    ├── gather_context()                ← Rev 02 — chat_context_service.py
    ├── (no evidence → fallback)
    ├── _build_user_prompt()
    └── chat_provider.complete()        ← Rev 01 — OllamaChatProvider
    │
    ▼
ChatResponse → JSON
    (or ChatCompletionError → HTTP 503)
```

## Guardrails

| Guard | Where enforced | Behaviour |
|-------|---------------|-----------|
| Empty / missing message | Pydantic `ChatRequest` | HTTP 422 |
| Message > 500 chars | Pydantic `ChatRequest` | HTTP 422 |
| No evidence (unsupported / no data) | `handle_chat` in Rev 03 | Returns fallback answer, no LLM call |
| Answer > 1000 chars | `handle_chat` in Rev 03 | Truncated before returning |
| `ChatCompletionError` (Ollama down/timeout) | `chat()` endpoint | HTTP 503 with Ollama-specific message |

## Scope Implemented

- `habittracker/api/v1/chat.py` — `POST /api/v1/chat`, module-level provider singletons, HTTP 503 on `ChatCompletionError`
- `habittracker/server.py` — registered `chat` router under `/api/v1`
- `tests/habittracker/api/__init__.py` + `tests/habittracker/api/v1/__init__.py` — new test hierarchy
- `tests/habittracker/api/v1/test_chat_endpoint.py` — 12 tests: happy path, request validation, 503 guardrail
- Total test count: 142 (up from 130 in Rev 03)

## Files Changed

- `backend/habittracker/api/v1/chat.py` — new
- `backend/habittracker/server.py` — added `chat` import + router registration
- `backend/tests/habittracker/api/__init__.py` — new
- `backend/tests/habittracker/api/v1/__init__.py` — new
- `backend/tests/habittracker/api/v1/test_chat_endpoint.py` — new
- `docs/implementation/phase-05-rev04.md` — this file

## Notes

- The `DeprecationWarning` about `asyncio.iscoroutinefunction` comes from FastAPI's internals on Python 3.14 — not our code. It does not affect behaviour.
- The endpoint does not log the user's message to avoid capturing PII in server logs. `chat_service.py` logs the intent and answer length only.

## Next Step

Phase 05 complete. Phase 06 — LangGraph orchestration:
- Replace the sequential `handle_chat` pipeline with a LangGraph state machine
- Add multi-turn memory via `thread_id`
- Introduce tool-calling nodes for each intent
- Keep the same `POST /api/v1/chat` contract — LangGraph is an internal implementation detail
