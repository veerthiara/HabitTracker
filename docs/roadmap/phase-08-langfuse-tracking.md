# Phase 08 — Langfuse Observability

## Goal

Integrate self-hosted Langfuse to give full observability into the LangGraph chat pipeline — per-node timing, inputs, outputs, and LLM call details — without requiring cloud accounts or sending data offsite.

## Current State

- LangGraph chat pipeline (Phase 06) is complete and running locally
- Phase 07 exposed chat through the UI
- No tracing or observability exists; production debugging relies on logs only

## Target Outcome

- Local Langfuse stack running via `make langfuse-up`
- Every `POST /api/v1/chat` invocation traced end-to-end in Langfuse UI
- Tracing is opt-in: absent env vars = zero overhead, no code changes needed by contributors
- Backend gracefully degrades if Langfuse is unavailable

---

## Architecture

```
POST /api/v1/chat
      │
      ├─ get_langfuse_callback_handler()   # returns handler or None
      │
      ├─ config["callbacks"] = [handler]   # only if enabled
      │
      └─ _graph.invoke(state, config)
              │
              ├─ classify_intent_node   ──▶ Langfuse trace (auto)
              ├─ gather_context_node    ──▶ Langfuse trace (auto)
              └─ generate_answer_node  ──▶ Langfuse trace (auto)
                                                │
                                                ▼
                                   Langfuse Server (localhost:3000)
```

---

## Revisions

### Rev 01 — Local Langfuse Stack

#### Scope
- Add `infra/local/langfuse/docker-compose.yml` — Langfuse server + dedicated Postgres
- Add `infra/local/langfuse/.env.example` — default local dev credentials and keys
- Add Makefile targets: `langfuse-up`, `langfuse-down`, `langfuse-logs`, `langfuse-ps`, `langfuse-reset`
- Add `docs/architecture/local-infrastructure.md`
- Add `infra/local/langfuse/README.md` with setup and integration guide

#### Deliverable
- Developer can run `make langfuse-up` and access Langfuse UI at `localhost:3000`
- No backend code changes yet

#### Out of scope
- Backend integration

---

### Rev 02 — Backend Langfuse Integration

#### Scope
- Add `langfuse` and `langchain` to `backend/pyproject.toml`
- Create `backend/habittracker/core/langfuse_integration.py`
  - `is_langfuse_enabled() -> bool`
  - `get_langfuse_callback_handler() -> CallbackHandler | None`
  - Opt-in via env vars: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`
  - `LANGFUSE_TRACING_ENABLED=false` override
  - Graceful degradation: returns `None` on missing keys or import failure
- Wire callback handler into `backend/habittracker/api/v1/chat.py`
- Add `backend/.env.example` documenting all env vars
- Add config docs to `backend/habittracker/core/config.py`
- Add 9 tests for langfuse integration module

#### Deliverable
- With Langfuse running and env vars set, every chat request appears as a trace in Langfuse UI
- Without env vars, backend behaves identically to before

#### Out of scope
- Custom spans or manual instrumentation beyond the callback handler
- Langfuse dashboards or alerting
