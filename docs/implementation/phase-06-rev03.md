# Phase 06 Rev 03 — End-to-End Graph Integration Test

## Goal

Validate the full LangGraph pipeline with `graph.invoke()` — all intent paths,
the UNSUPPORTED shortcut, the no-evidence fallback, the answer length cap, and
the `ChatResponse` schema mapping.  No endpoint changes; `handle_chat` remains
active.

## Key Decisions

- **Single integration test file, no new production code.**  The nodes, routing,
  and builder from Rev 02 are already complete.  Rev 03 is purely the validation
  layer that proves the graph runs correctly end-to-end.

- **Mock boundary: `habittracker.graph.nodes.gather_context`.**  Patching at
  the import site inside `nodes.py` intercepts the call regardless of which
  node invokes it.  Sessions and embed providers are `MagicMock` — the graph
  carries them in state but they never reach real I/O.

- **`ChatContextResult()` as the default empty mock.**  When testing the
  UNSUPPORTED shortcut, the monkeypatched `gather_context` must never actually
  be called.  A side-effect list (`gather_called`) confirms the routing edge
  skipped `gather_context_node` entirely.

- **`ChatResponse` construction from state fields.**  The contract test
  explicitly builds a `ChatResponse` from the final graph state.  If the state
  fields ever drift from the response schema this test fails immediately —
  making the mapping an enforced invariant rather than a comment.

- **`thread_id` included in initial state.**  It is an input field on
  `ChatGraphState` (added in Rev 01) so it is passed in `_base_state()`.
  No checkpointer is configured yet, so it flows through state but has no
  effect on routing or checkpointing.

## Architectural Context

```
habittracker/
    graph/
        state.py    ← unchanged
        nodes.py    ← unchanged
        routing.py  ← unchanged
        builder.py  ← unchanged
tests/
    habittracker/graph/
        test_routing.py          ← Rev 02
        test_nodes.py            ← Rev 02
        test_graph_integration.py ← Rev 03 (new)
```

The live endpoint still calls `handle_chat`.  The integration tests prove
`graph.invoke()` produces state that maps cleanly to the same `ChatResponse`
schema that `handle_chat` returns — establishing the equivalence needed before
the endpoint switch in Rev 05.

## Scope Implemented

- `tests/habittracker/graph/test_graph_integration.py` — 14 integration tests:
  - `TestGraphHappyPath` (4): BOTTLE_ACTIVITY, HABIT_SUMMARY, NOTE_PATTERN, GENERAL
  - `TestGraphUnsupportedShortcut` (2): greeting, short message — gather skipped
  - `TestGraphNoEvidenceFallback` (2): supported intent + empty evidence → fallback
  - `TestGraphAnswerCap` (2): truncation at MAX_ANSWER_LEN, no truncation below cap
  - `TestGraphResponseContract` (4): all fields present, EvidenceItem types,
    intent is string, ChatResponse built from state without error

Total tests: 181 (up from 167 in Rev 02). All pass.

## Files Changed

```
backend/tests/habittracker/graph/test_graph_integration.py
docs/implementation/phase-06-rev03.md
```

## Notes

- No production code changed in Rev 03 — the graph was fully assembled in Rev 02.
  This revision is a pure validation checkpoint consistent with the phase plan.

## Next Step

Rev 04 — `thread_id` + `MemorySaver` checkpointer:
- `ChatRequest` gains `thread_id: str | None = None`
- `ChatResponse` gains `thread_id: str`
- `build_chat_graph` compiled with `MemorySaver`
- Server generates UUID when client omits `thread_id`
- Test: two invocations on same `thread_id` share checkpoint state
