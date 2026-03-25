# Phase 06 Rev 02 — Graph Nodes, Routing, and Builder

## Goal

Define all three LangGraph nodes, the conditional routing function, and the
graph builder.  The pipeline compiles end-to-end and every node is covered by
unit tests.  No endpoint changes — `handle_chat` remains active.

## Key Decisions

- **Factory pattern for provider-dependent nodes.**  `gather_context_node` and
  `generate_answer_node` require providers (embed, chat).  Rather than relying
  on global singletons or LangGraph `RunnableConfig`, each is created via a
  `make_*_node(provider)` factory.  The factory closes over the provider, so
  the node signature stays `(state) -> dict` — exactly what LangGraph expects.
  This also makes nodes trivially testable: inject a mock provider into the
  factory, call the returned function directly.

- **`classify_intent_node` is a plain function.**  It has no I/O and needs no
  factory.  This asymmetry is intentional — it mirrors the fact that the
  underlying `classify_intent()` is pure.

- **No MemorySaver in Rev 02.**  Adding a checkpointer requires passing
  `thread_id` in every `graph.invoke(config=...)`.  Since `thread_id` is not
  yet on `ChatRequest`, keeping the graph checkpointer-free in this revision
  avoids thread-id boilerplate in every test.  MemorySaver is added in Rev 04
  alongside the `ChatRequest` schema change.

- **`generate_answer_node` uses `evidence` from state with `.get()` fallback.**
  When the UNSUPPORTED routing path calls `generate_answer_node` directly
  (skipping `gather_context_node`), the `evidence` key has never been written
  to state.  Using `state.get("evidence") or []` is safe at runtime because
  TypedDict is purely a type-annotation tool — the underlying object is a
  plain dict.

- **Constants imported from `chat_service`, prompt builder inlined.**
  `FALLBACK_ANSWER`, `MAX_ANSWER_LEN`, and `SYSTEM_PROMPT` are module-level
  constants in `chat_service.py` — importing them avoids duplication.  The
  prompt template (`Data:\n{context}\n\nQuestion: {message}`) is one line so
  it is inlined in the node rather than importing the private `_build_user_prompt`.

- **Test message for NOTE_PATTERN excludes habit keywords.**  The classifier
  checks `HABIT_SUMMARY` before `NOTE_PATTERN`.  A message containing "habit"
  never reaches the pattern check.  The test uses a habit-free message
  (`"Why do I always feel tired on Fridays?"`) to exercise the NOTE_PATTERN
  branch correctly — consistent with the documented classifier precedence.

## Architectural Context

```
habittracker/
    graph/
        __init__.py     ← Rev 01
        state.py        ← Rev 01
        nodes.py        ← Rev 02 (new)
        routing.py      ← Rev 02 (new)
        builder.py      ← Rev 02 (new)
    services/
        chat_service.py ← handle_chat still active (unchanged)
    api/v1/
        chat.py         ← still calls handle_chat (unchanged)
```

Graph topology compiled in Rev 02:

```
[START]
   │
   ▼
classify_intent_node
   │
   ├── UNSUPPORTED ──────────────────────────────▶ generate_answer_node
   │                                                   (returns FALLBACK_ANSWER)
   └── all others ──▶ gather_context_node
                             │
                             ▼
                      generate_answer_node
                             │
                             ▼
                           [END]
```

## Scope Implemented

- `habittracker/graph/nodes.py`
  - `classify_intent_node(state)` — wraps `classify_intent()`, writes `intent`
  - `make_gather_context_node(embed_provider)` — factory; wraps `gather_context()`,
    writes `evidence`, `context_text`, `used_notes`
  - `make_generate_answer_node(chat_provider)` — factory; calls LLM or returns
    fallback; writes `answer`

- `habittracker/graph/routing.py`
  - `intent_router(state)` — pure function; returns `"generate_answer"` for
    UNSUPPORTED, `"gather_context"` for all other intents

- `habittracker/graph/builder.py`
  - `build_chat_graph(embed_provider, chat_provider)` — assembles and compiles
    the StateGraph; no checkpointer (Rev 04)

- `tests/habittracker/graph/__init__.py` — new test package
- `tests/habittracker/graph/test_routing.py` — 7 tests for `intent_router`
- `tests/habittracker/graph/test_nodes.py` — 18 tests: classify (6),
  gather_context (4), generate_answer (5), builder smoke (2)

Total tests: 167 (up from 142 in Rev 01). All pass.

## Files Changed

```
backend/habittracker/graph/nodes.py
backend/habittracker/graph/routing.py
backend/habittracker/graph/builder.py
backend/tests/habittracker/graph/__init__.py
backend/tests/habittracker/graph/test_routing.py
backend/tests/habittracker/graph/test_nodes.py
docs/implementation/phase-06-rev02.md
```

## Notes

- The Pydantic V1 warning from `langchain-core` on Python 3.14 persists across
  all LangGraph imports.  It is upstream noise and does not affect behaviour.
- `graph.get_graph().nodes` confirms node names in the builder smoke test —
  this validates the wiring without doing a full graph invocation.

## Next Step

Rev 03 — end-to-end integration:
- Full `graph.invoke(initial_state)` round-trip with mock providers
- Result validated against the schema returned by `handle_chat`
- `handle_chat` still owns the live endpoint (not switched until Rev 05)
