# Phase 05 Rev 01 — Chat Provider + Schemas

## Goal

Lay the foundation for the AI chat system: a `ChatProvider` abstraction, an `OllamaChatProvider` implementation that calls a local Ollama model, stable API schemas, and a correctly structured test suite that mirrors the application folder hierarchy.

## Key Decisions

### Chat model choice: `llama3.2`

The project already has `nomic-embed-text` for embeddings (768 dims) and several Ollama models locally available (`qwen2.5-coder:7b/14b/32b`, `llama3.2`, `gemma3:270m`). `llama3.2` (3B) was chosen as the default chat model — it is fast, already pulled, and handles structured Q&A well. The choice is fully overridable via `OLLAMA_CHAT_MODEL` env var with zero code changes.

### Two separate provider ABCs, same `base.py`

`EmbeddingProvider` (Phase 04) and the new `ChatProvider` are kept in the same `habittracker/providers/base.py` module. The two ABCs cover fundamentally different operations (`embed() → list[float]` vs `complete() → str`) and having them co-located makes the abstraction layer easy to find. A separate `chat_provider.py` would add indirection for no benefit.

### Timeout is not retried — intentional

For embedding (`OllamaProvider`), timeouts are retried alongside 5xx/connect errors. For chat (`OllamaChatProvider`), timeouts are raised immediately without retry. The reasoning: embedding requests are short and fast; a timeout usually means a transient network blip. Chat completions on a local 3B model can take 30–120 seconds — a timeout most likely means the model is overloaded or hung. Retrying a hung model makes things worse. This decision was explicitly requested during planning.

### Separate timeout config for chat

`OLLAMA_CHAT_TIMEOUT_SEC` (default: 120s) is separate from `OLLAMA_TIMEOUT_SEC` (embedding, default: 60s). Chat completions are inherently slower than embedding; a shared timeout would either be too tight for chat or too loose for embeddings.

### `include_notes` removed from request

The original roadmap plan had `include_notes: bool` in `ChatRequest`. This was removed — the system should decide whether to use semantic search based on intent, not the caller. Exposing that toggle would couple the client to internal routing decisions and invite misuse.

### `user_id` removed from request body

All other endpoints use `get_current_user_id()` as a FastAPI dependency. The chat endpoint follows the same pattern — no user ID in the request body.

### `used_notes` and `evidence` in response — forward-compatible

`ChatResponse` includes `used_notes: bool` and `evidence: list[EvidenceItem]` even though this rev doesn't produce actual evidence yet. These fields are the stable contract for Phase 06 (LangGraph) and Phase 07 (UI) which need to know:
- Did the answer involve fuzzy pgvector data?
- What structured facts were used?

### `@patch` decorator over `with patch(...)` context manager

All tests now use the `@patch` / `@patch.object` decorator form instead of `with patch(...) as mock:` context managers. The decorator declares what is being mocked at the top of each test method — easier to scan, consistent with the `pytest.fixture` pattern, and removes nesting. Stacked `@patch` decorators are applied bottom-up, so the bottom decorator's mock argument arrives first after `self`.

### `@pytest.fixture` (no parentheses)

The empty-parens form `@pytest.fixture()` works but is unnecessary — parentheses are only required when passing arguments to the fixture decorator (e.g. `@pytest.fixture(scope="module")`). The no-parens form matches modern pytest convention and the pattern used elsewhere in the project.

### No `@pytest.mark.asyncio`

These tests are all synchronous (`def`, not `async def`). `@pytest.mark.asyncio` is only required for `async def test_...` functions. Not used here.

### `mock_post.call_count` replaces manual counter

The retry tests previously used a `call_count` variable with a closure-based side effect to count invocations. Since `@patch` gives us a `MagicMock` directly, `mock_post.call_count` provides the same information with no boilerplate.



Previously all tests lived under `tests/scripts/embed/` — a holdover from when the logic lived in `scripts/`. Now that all logic lives in `habittracker/`, the test structure mirrors the app:

```
tests/habittracker/
  providers/
    test_base.py           → habittracker/providers/base.py
    test_ollama.py         → habittracker/providers/ollama.py
    test_ollama_chat.py    → habittracker/providers/ollama_chat.py
  services/
    test_embedding_service.py → habittracker/services/embedding_service.py
  models/
    repository/
      test_embedding_repository.py → habittracker/models/repository/embedding_repository.py
```

## Architectural Context

```
POST /api/v1/chat (Rev 04)
       │
       ▼
habittracker/services/chat_service.py (Rev 03)
       │
       ├─ chat_intent_service.py (Rev 02)  ← classify message
       ├─ chat_data_service.py   (Rev 02)  ← gather evidence from repos
       │
       └─ habittracker/providers/ollama_chat.py  ← THIS REV
               implements
                   habittracker/providers/base.py (ChatProvider ABC)  ← THIS REV
               configured by
                   habittracker/core/config.py (OLLAMA_CHAT_MODEL, OLLAMA_CHAT_TIMEOUT_SEC)  ← THIS REV
```

## Scope Implemented

- `habittracker/core/config.py` — added `OLLAMA_CHAT_MODEL` (default: `llama3.2`), `OLLAMA_CHAT_TIMEOUT_SEC` (default: 120s); split retry/backoff settings into shared constants
- `habittracker/providers/base.py` — added `ChatProvider` ABC with `complete(system, user) → str`; added `ChatCompletionError(RuntimeError)`
- `habittracker/providers/ollama_chat.py` — `OllamaChatProvider` calling `/api/chat`, retry on 5xx/connect, immediate raise on timeout and 4xx
- `habittracker/schemas/chat.py` — `ChatRequest`, `EvidenceItem`, `ChatResponse`
- Test restructure: `tests/scripts/embed/` deleted; new `tests/habittracker/` tree created to mirror app

## Files Changed

```
backend/habittracker/core/config.py
backend/habittracker/providers/base.py
backend/habittracker/providers/ollama_chat.py     ← new
backend/habittracker/schemas/chat.py              ← new
backend/tests/habittracker/__init__.py            ← new
backend/tests/habittracker/providers/__init__.py  ← new
backend/tests/habittracker/providers/test_base.py ← new (replaces scripts/embed version)
backend/tests/habittracker/providers/test_ollama.py ← new (replaces scripts/embed version)
backend/tests/habittracker/providers/test_ollama_chat.py ← new
backend/tests/habittracker/services/__init__.py   ← new
backend/tests/habittracker/services/test_embedding_service.py ← new (replaces scripts/embed version)
backend/tests/habittracker/models/__init__.py     ← new
backend/tests/habittracker/models/repository/__init__.py ← new
backend/tests/habittracker/models/repository/test_embedding_repository.py ← new (replaces scripts/embed version)
backend/tests/scripts/                            ← deleted
```

## Notes

- 54/54 tests passing (36 carried over + 13 new `OllamaChatProvider` tests + 5 new `ChatProvider`/`ChatCompletionError` tests in `test_base.py`)
- `OllamaChatProvider` is not wired into any endpoint yet — that happens in Rev 04
- No new Alembic migration needed

## Next Step

Rev 02 — intent classification (`chat_intent_service.py`) + data gathering (`chat_data_service.py`).
