# Phase 06 Rev 05 — Endpoint Switch to LangGraph

## Goal

Replace the direct `handle_chat()` call in `POST /api/v1/chat` with the LangGraph graph built across Rev 01–04. This is the live switchover: the endpoint now drives all intent classification, context retrieval, and answer generation through the graph.

## Key Decisions

- **Session injected via `config["configurable"]["session"]` instead of graph state.** MemorySaver serialises the full graph state via msgpack between checkpoints. SQLAlchemy `Session` objects are not msgpack-serialisable. Moving session to the LangGraph config sidesteps serialisation entirely — config is never checkpointed.

- **`gather_context_node` updated to `(state, config)` signature.** LangGraph automatically passes the invocation config as the second argument when a node function accepts two positional parameters. The node reads `config.get("configurable", {}).get("session")`.

- **`session` field removed from `ChatGraphState`.** State only holds serialisable data. Session is an ephemeral, per-request dependency — it never needs to survive across turns.

- **Module-level `_graph` singleton.** Providers and `MemorySaver` are constructed once at import time and reused across requests. This is the same pattern used for the embed/chat providers in earlier phases.

- **`handle_chat` kept in `chat_service.py` but no longer called from the endpoint.** Preserved as a reference implementation and for test isolation if needed later.

- **`thread_id` generated on the server if not supplied.** The UUID is forwarded as both `state["thread_id"]` and `config["configurable"]["thread_id"]` (required by MemorySaver to index the checkpoint).

## Architectural Context

This revision closes the loop on the phase-06 LangGraph migration. Revisions 01–04 built and tested the graph components (state, nodes, routing, builder, persistence) in isolation. Rev 05 wires the graph into the API layer.

```
ChatRequest
    │
    ▼
POST /api/v1/chat (chat.py)
    │  resolves thread_id, builds initial_state, config
    ▼
_graph.invoke(initial_state, config=config)
    │
    ├─ classify_intent_node(state)          ← pure keyword routing
    ├─ [route: UNSUPPORTED → generate_answer_node]
    ├─ gather_context_node(state, config)  ← reads session from config
    └─ generate_answer_node(state)          ← LLM or fallback
    │
    ▼
ChatResponse(answer, intent, used_notes, evidence, thread_id)
```

## Scope Implemented

- `habittracker/graph/state.py` — removed `session: Any` field; removed `Any` import
- `habittracker/graph/nodes.py` — `gather_context_node` now accepts `(state, config)` and reads `session` from `config["configurable"]["session"]`
- `habittracker/api/v1/chat.py` — fully rewritten: imports `build_chat_graph` + `MemorySaver`; module-level `_graph` singleton; endpoint builds state + config, calls `_graph.invoke`, maps result to `ChatResponse`
- `tests/habittracker/graph/test_nodes.py` — removed `session` from `_make_state()`; added `_config()` helper; all `gather_context_node` calls now pass `config` as second arg
- `tests/habittracker/graph/test_graph_integration.py` — removed `session` from `_base_state()`; added `_config()` helper; all `graph.invoke()` calls pass `config=_config()`
- `tests/habittracker/graph/test_thread_persistence.py` — moved `session=None` from state dict to `config["configurable"]["session"]`
- `tests/habittracker/api/v1/test_chat_endpoint.py` — patch target changed from `handle_chat` to `_graph.invoke`; mock returns a state dict; added `thread_id` assertions; two new tests (`test_response_contains_thread_id`, `test_client_thread_id_echoed_in_response`)

## Files Changed

```
habittracker/graph/state.py
habittracker/graph/nodes.py
habittracker/api/v1/chat.py
tests/habittracker/graph/test_nodes.py
tests/habittracker/graph/test_graph_integration.py
tests/habittracker/graph/test_thread_persistence.py
tests/habittracker/api/v1/test_chat_endpoint.py
docs/implementation/phase-06-rev05.md
```

## Notes

- 194 tests pass (up from 192 in Rev 04; 2 new endpoint tests for `thread_id`).
- `handle_chat` in `chat_service.py` is dead code after this revision. It will be removed or repurposed in a future cleanup pass.
- MemorySaver holds state in process memory. A server restart clears all thread checkpoints — expected for dev. Production would swap in a persistent checkpointer (e.g. Postgres-backed).
- The `(state, config)` node signature is standard LangGraph — no import of `RunnableConfig` is required for the pattern to work.

## Next Step

Phase 06 complete. Next: Phase 07 — UI polish (connect React frontend to the live graph endpoint, display `evidence` cards, thread continuity via `thread_id`).
