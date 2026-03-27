# Phase 06 Rev 01 — LangGraph Foundation + State

## Goal

Add the `langgraph` dependency and introduce the `habittracker/graph` package
with `ChatGraphState` — the shared state TypedDict that will flow through the
graph pipeline in subsequent revisions.  No behaviour changes in this revision.

## Key Decisions

- **`langgraph >= 0.2` added as a runtime dependency** — resolves to 1.1.3.
  `MemorySaver` (Rev 04) and `StateGraph` (Rev 02) are both included in the
  core package; no extra checkpoint package needed yet.
- **`ChatGraphState` defined in its own `state.py`** — keeps the state
  definition isolated from nodes, routing, and builder logic.  Each of those
  gets its own module in Rev 02.
- **`session` typed as `Any` in the state** — avoids a hard SQLAlchemy import
  in the state module.  The actual `Session` type is enforced at the call site
  (the endpoint and nodes).  TypedDict fields don't participate in runtime
  validation so there is no practical downside.
- **`clarify: str | None` added now as a placeholder** — per the detailed plan,
  it is scaffolded here so Rev 02 nodes can reference the field without a
  schema change.  Always `None` in Phase 06.
- **`thread_id: str` is an input field** — it is resolved before `graph.invoke()`
  is called (server generates UUID if client omits it).  The state carries it
  through so the endpoint can return it in `ChatResponse`.

## Architectural Context

```
habittracker/
    graph/              ← new package (Rev 01)
        __init__.py     ← package docstring + revision roadmap
        state.py        ← ChatGraphState TypedDict
    services/
        chat_service.py ← handle_chat still active (unchanged)
    api/v1/
        chat.py         ← still calls handle_chat (unchanged)
```

The graph package is inert in this revision — no nodes, no routing, no builder.
The endpoint and all existing tests are untouched.

## Scope Implemented

- `langgraph >= 0.2` added to `[tool.poetry.dependencies]` in `pyproject.toml`
- `poetry.lock` updated (langgraph 1.1.3 + deps: langchain-core, langgraph-checkpoint, langgraph-sdk, langsmith, etc.)
- `backend/habittracker/graph/__init__.py` — package docstring with revision roadmap
- `backend/habittracker/graph/state.py` — `ChatGraphState` TypedDict (10 fields)
- All 142 existing tests pass

## Files Changed

```
backend/pyproject.toml
backend/poetry.lock
backend/habittracker/graph/__init__.py
backend/habittracker/graph/state.py
docs/implementation/phase-06-rev01.md
```

## Notes

- `langgraph StateGraph` imports produce a `UserWarning` about Pydantic V1
  compatibility on Python 3.14 from `langchain-core` internals.  This is
  upstream noise — not our code, does not affect behaviour.
- `langgraph 1.1.3` is the resolved version under `>= 0.2`.  If a future
  revision requires a tighter bound it can be pinned then.

## Next Step

Rev 02 — `nodes.py`, `routing.py`, `builder.py`:
- Define `classify_intent_node`, `gather_context_node`, `generate_answer_node`
- Add `intent_router` conditional edge
- Compile the graph with a `MemorySaver` placeholder
- Unit tests for each node in isolation
