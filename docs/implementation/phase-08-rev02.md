# Phase 08 Rev 02 — Backend Langfuse Integration

## Goal

Add optional Langfuse tracing to the LangGraph chat pipeline so that every chat request can be observed end-to-end in a Langfuse dashboard — including per-node timing, inputs, and outputs.

## Key Decisions

**1. Opt-in via environment variables.**
Langfuse tracing activates only when `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` are all set. When any are missing, tracing is silently disabled with zero overhead. This keeps the dev experience unchanged for contributors who don't use Langfuse.

**2. Use Langfuse's LangChain CallbackHandler.**
The `langfuse.langchain.CallbackHandler` is the recommended integration for LangChain/LangGraph. When passed as a callback to `graph.invoke()`, it automatically instruments every node execution — no manual span management required. This required adding `langchain` as an explicit dependency (previously only `langchain-core` was present as a transitive dep of `langgraph`).

**3. Fresh handler per request.**
`get_langfuse_callback_handler()` creates a new `CallbackHandler` instance per call. This ensures each request gets its own trace context, which is the recommended pattern for web frameworks.

**4. Graceful degradation.**
If the `CallbackHandler` creation fails (e.g. network error to Langfuse, import failure), the function returns `None` and the request proceeds without tracing. A warning is logged for operators.

## Architectural Context

```
                     ┌───────────────────────────────────────┐
                     │         Langfuse Server               │
                     │   (local: http://localhost:3000)       │
                     └──────────────┬────────────────────────┘
                                    │ traces
                                    │
POST /api/v1/chat ──▶ chat()       │
                      │             │
                      ├─ get_langfuse_callback_handler()
                      │   └─ returns CallbackHandler or None
                      │
                      ├─ config["callbacks"] = [handler]  (if enabled)
                      │
                      └─ _graph.invoke(state, config)
                           │
                           ├─ classify_intent  ──▶ trace span
                           ├─ gather_context   ──▶ trace span
                           └─ generate_answer  ──▶ trace span
```

When tracing is disabled, `config["callbacks"]` is not set and the graph runs identically to before.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | Yes (to enable) | — | Project public key from Langfuse settings |
| `LANGFUSE_SECRET_KEY` | Yes (to enable) | — | Project secret key from Langfuse settings |
| `LANGFUSE_BASE_URL` | Yes (to enable) | — | Langfuse server URL (e.g. `http://localhost:3000`) |
| `LANGFUSE_TRACING_ENABLED` | No | `true` | Set to `false` to disable even when keys are set |

## Scope Implemented

- `backend/pyproject.toml` — added `langfuse >=4.0` and `langchain >=1.0` dependencies
- `backend/habittracker/core/langfuse_integration.py` — **new**: optional Langfuse client module with `is_langfuse_enabled()` and `get_langfuse_callback_handler()`
- `backend/habittracker/core/config.py` — updated module docstring with Langfuse env var documentation
- `backend/habittracker/api/v1/chat.py` — attach Langfuse CallbackHandler to graph invocation config when enabled
- `backend/.env.example` — **new**: documents all backend env vars including Langfuse
- `backend/tests/habittracker/core/__init__.py` — **new**: test package init
- `backend/tests/habittracker/core/test_langfuse_integration.py` — **new**: 9 tests covering enabled/disabled states, graceful degradation

## Files Changed

```
backend/pyproject.toml
backend/poetry.lock
backend/habittracker/core/config.py
backend/habittracker/core/langfuse_integration.py       ← new
backend/habittracker/api/v1/chat.py
backend/.env.example                                     ← new
tests/habittracker/core/__init__.py                      ← new
tests/habittracker/core/test_langfuse_integration.py     ← new
docs/implementation/phase-08-rev02.md                    ← new (renamed from phase-07-rev01.md)
```

## Notes

- 211 tests pass (202 existing + 9 new).
- No existing tests were modified or removed.
- The `langchain` package was added as an explicit dependency because Langfuse's `CallbackHandler` requires it (not just `langchain-core`). Since `langchain-core` was already a transitive dependency of `langgraph`, this addition is lightweight.
- The integration is fully backward-compatible: without Langfuse env vars, the app behaves identically to Phase 06.

## Next Step

- Run `make langfuse-up`, copy `infra/local/langfuse/.env.example` to `.env`, and verify traces appear in the Langfuse UI at `localhost:3000` after sending a chat message.
- Consider adding Langfuse tracing to the embedding pipeline (`scripts/embed/`) for batch observability.
