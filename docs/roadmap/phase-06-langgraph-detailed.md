# Phase 06 — LangGraph Orchestration (Detailed Plan)

## Goal

Replace the sequential `handle_chat()` pipeline with a LangGraph state machine.
The `/api/v1/chat` response contract stays identical — LangGraph is an internal
implementation detail invisible to clients.

---

## Key Design Principles

### 1. Graph replaces `handle_chat` — everything else stays

`chat_intent_service`, `chat_context_service`, their repositories, and all
existing tests remain unchanged.  The graph wraps them as nodes; the services
themselves are not refactored.

### 2. State is explicit — no ambient globals

All data flowing through the graph travels as typed fields on `ChatGraphState`.
Nodes read from state, write to state.  No singletons or closures for in-flight
data.

### 3. Routing is structural, not conditional inside a function

Intent → branch selection is a LangGraph conditional edge.
`STRUCTURED_ONLY` intents (`bottle_activity`, `habit_summary`) → skip the
semantic-search node entirely.
`NOTE_REQUIRED` intents (`note_pattern`, `general`) → execute the semantic node.

### 4. Providers are injected at graph-compile time, not at node definition

`OllamaProvider` and `OllamaChatProvider` are passed into the graph builder.
Nodes reference them from graph config, not from module-level singletons.
This makes the graph testable by injecting mock providers.

### 5. Checkpointer is pluggable from day one

Rev 04 uses `MemorySaver` (in-memory, no setup needed for local dev).
The checkpointer is passed in at compile time so Postgres-backed persistence
can be swapped in later with zero node changes.

### 6. `thread_id` comes from the client

`ChatRequest` gains an optional `thread_id: str | None`.  If `None`, the server
generates a UUID for that request — this gives a valid thread but no cross-
request continuity.  If the client provides a stable `thread_id`, the
checkpointer preserves conversation state across calls on that thread.

### 7. Sync graph, sync endpoint — no async for now

All current services and providers are sync.  LangGraph supports sync graphs.
Using `graph.invoke()` (sync) avoids having to migrate the entire stack to
`async`.  Async can be added in a later revision if needed.

### 8. `thread_id` is returned in the response

`ChatResponse` gains one field: `thread_id: str`.  If the client omits it in
the request, the server generates a UUID and returns it so the frontend can
pin it for the next turn.  All other fields — `answer`, `intent`,
`used_notes`, `evidence` — are unchanged.

---

## LangGraph Dependency

```
langgraph >= 0.2          # core graph + MemorySaver
```

No `langgraph-checkpoint-postgres` for now (deferred to long-term memory phase).

---

## Graph Package Structure

```
backend/habittracker/
    graph/
        __init__.py
        state.py           # ChatGraphState TypedDict
        nodes.py           # classify_intent_node, gather_context_node,
                           # generate_answer_node
        routing.py         # intent_router() conditional edge function
        builder.py         # build_chat_graph(embed_provider, chat_provider)
```

---

## State Definition

```python
# graph/state.py

class ChatGraphState(TypedDict):
    # inputs (populated before graph.invoke)
    user_id:      uuid.UUID
    session:      Session          # SQLAlchemy session passed through
    message:      str
    thread_id:    str              # always set — server-generated if client omitted

    # populated by classify_intent_node
    intent:       str              # ChatIntent value

    # populated by gather_context_node
    evidence:     list[EvidenceItem]
    context_text: str
    used_notes:   bool

    # populated by generate_answer_node
    answer:       str

    # scaffolding for future clarify step (Phase 07)
    clarify:      str | None       # always None in Phase 06
```

---

## Node Definitions

### `classify_intent_node`
- Reads: `state["message"]`
- Calls: `classify_intent(message)` from `chat_intent_service`
- Writes: `state["intent"]`

### `gather_context_node`
- Reads: `state["session"]`, `state["user_id"]`, `state["intent"]`, `state["message"]`
- Calls: `gather_context(...)` from `chat_context_service`
- Writes: `state["evidence"]`, `state["context_text"]`, `state["used_notes"]`
- Note: this one node handles all intents. Routing determines *whether* it runs
  the semantic path internally (it already does this via the intent enum).

### `generate_answer_node`
- Reads: `state["evidence"]`, `state["context_text"]`, `state["message"]`
- Calls: `_build_user_prompt()` + `chat_provider.complete()` (same as Rev 03 of Phase 05)
- If `evidence` is empty → writes fallback answer, never calls LLM
- Writes: `state["answer"]`

---

## Graph Topology

```
[START]
   │
   ▼
classify_intent_node
   │
   ├── (conditional edge: intent_router)
   │
   ├── UNSUPPORTED ──────────────────────────────────────────▶ generate_answer_node
   │                                                               (writes fallback)
   │
   └── BOTTLE / HABIT / NOTE_PATTERN / GENERAL ──▶ gather_context_node
                                                          │
                                                          ▼
                                                   generate_answer_node
                                                          │
                                                          ▼
                                                        [END]
```

The `UNSUPPORTED` shortcut skips `gather_context_node` entirely — mirrors the
early-exit behaviour that exists in `handle_chat` today.

---

## Routing Logic

```python
# graph/routing.py

def intent_router(state: ChatGraphState) -> str:
    if state["intent"] == ChatIntent.UNSUPPORTED.value:
        return "generate_answer"    # skip context — write fallback directly
    return "gather_context"
```

---

## `thread_id` + Checkpointer (Rev 04)

```python
# ChatRequest gains:
thread_id: str | None = None   # optional, client-generated or server-assigned

# In the endpoint:
thread_id = request.thread_id or str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}
result = graph.invoke(initial_state, config=config)
```

`MemorySaver` is compiled in once at app startup and shared across requests.
Each `thread_id` gets its own checkpoint slot in memory.  Restart clears all
threads (expected for dev).

---

## Endpoint Changes (Rev 05)

`habittracker/api/v1/chat.py` changes:

| Before | After |
|--------|-------|
| `from habittracker.services.chat_service import handle_chat` | `from habittracker.graph.builder import build_chat_graph` |
| `result = handle_chat(session, user_id, request, ...)` | `result = graph.invoke(state, config=config)` |
| N/A | `thread_id = request.thread_id or str(uuid.uuid4())` |
| `return ChatResponse(...)` | `return ChatResponse(..., thread_id=thread_id)` |

Module-level:
- `_embed_provider = OllamaProvider()` stays
- `_chat_provider = OllamaChatProvider()` stays
- `_graph = build_chat_graph(_embed_provider, _chat_provider)` added — compiled once
- `handle_chat` import removed from this file; function remains in `chat_service.py`

---

## API Contract Delta

`ChatRequest` gains one optional field — backward-compatible:

```json
{
  "message": "...",
  "thread_id": "abc-123"     // optional — server generates if omitted
}
```

`ChatResponse` gains `thread_id` — the server always echoes the resolved ID:

```json
{
  "answer": "...",
  "intent": "bottle_activity",
  "used_notes": false,
  "evidence": [...],
  "thread_id": "abc-123"     // server-generated UUID if client did not send one
}
```

Existing clients that ignore unknown fields are unaffected (standard Pydantic
behavior: extra fields in a response never break a client that doesn't read them).

---

## Revision Breakdown

### Rev 01 — LangGraph foundation + state
**Deliverable:** package scaffolding + `ChatGraphState` — no behaviour change

- Add `langgraph` to `pyproject.toml`
- Create `habittracker/graph/__init__.py`, `state.py`
- Define `ChatGraphState` TypedDict
- Verify import works (`poetry run python -c "from habittracker.graph.state import ChatGraphState"`)

**Not included:** nodes, routing, builder, any endpoint change

---

### Rev 02 — Nodes + routing
**Deliverable:** all three nodes + conditional edge defined, graph compiles

- Add `nodes.py`: `classify_intent_node`, `gather_context_node`, `generate_answer_node`
- Add `routing.py`: `intent_router`
- Add `builder.py`: `build_chat_graph` — compiles graph with `MemorySaver`
- Unit tests for each node in isolation (mock session, mock providers)

**Not included:** endpoint wired to graph, `thread_id` on request

---

### Rev 03 — End-to-end graph + answer generation
**Deliverable:** graph runs full pipeline, result matches current `handle_chat` output

- `generate_answer_node` finalized: fallback + LLM path
- Integration test: full graph invocation with mock providers — validates
  output matches the schema returned by `handle_chat`
- `handle_chat` still used by the endpoint (not switched yet)

**Not included:** `thread_id`, checkpointer config, endpoint switch

---

### Rev 04 — `thread_id` + checkpointer
**Deliverable:** graph compiled with `MemorySaver`, `thread_id` threaded through

- `ChatRequest` gains `thread_id: str | None = None`
- `ChatResponse` gains `thread_id: str` (always populated)
- `ChatGraphState` gains `thread_id: str` and `clarify: str | None`
- `build_chat_graph` compiles with `MemorySaver` checkpointer
- Server generates a UUID if the client omits `thread_id`
- Test: two invocations on the same `thread_id` share checkpoint state
- `handle_chat` still used by the endpoint (not switched yet)

**Not included:** endpoint switch (Rev 05)

---

### Rev 05 — Endpoint switch + guardrails
**Deliverable:** `/api/v1/chat` runs through the graph, all existing tests pass

- `chat.py` endpoint switches from `handle_chat` → `_graph.invoke`
- `thread_id` resolved (client value or server UUID) and forwarded via `config`
- `thread_id` included in `ChatResponse` returned to the client
- `ChatCompletionError` → HTTP 503 guardrail preserved at the endpoint layer
- Existing 12 endpoint tests updated to assert `thread_id` in response body
- Graph-level integration tests added
- `handle_chat` remains in `chat_service.py`, not called, not deleted
  (treated as migration reference until Phase 07 cleanup)

---

### Rev 06 — Multi-Turn Conversation Memory
**Deliverable:** The graph accumulates a windowed conversation history across turns on the same `thread_id`. The LLM receives prior user/assistant pairs and can correctly answer follow-up references.

#### Scope

- Extend `ChatGraphState` with:
  - `current_message: str` — the raw user message for this turn (replaces using `state["message"]` directly in the generate node)
  - `messages: Annotated[list[ConversationTurn], operator.add]` — typed accumulation field; LangGraph reducer **appends** across checkpoint turns rather than overwriting
- Define `ConversationTurn` as a typed `TypedDict` (`role: str`, `content: str`) in `state.py` — avoids raw untyped dicts flowing through nodes
- `CONVERSATION_WINDOW = 10` turns (5 user + 5 assistant) — simple slice cap to avoid unbounded prompt growth; configured as a module constant
- `classify_intent_node` — appends `{"role": "user", "content": message}` to `messages` at turn start
- `generate_answer_node` — constructs multi-part LLM call with explicit separation of (A) conversational history and (B) current evidence; appends assistant answer to `messages` at turn end
- `ChatProvider.complete()` — upgraded to accept `messages: list[ConversationTurn]`; Ollama `/api/chat` already supports multi-turn natively
- `OllamaChatProvider.complete()` — updated signature; payload built from `messages` list directly
- System prompt structure separates **three trust levels**:
  1. `system` role: who the assistant is + ground rules
  2. Evidence block injected as the final `user` turn's content (verified DB/search data)
  3. Conversation history: prior `user`/`assistant` turns — labeled as "Conversation history" and explicitly noted not to be treated as verified data
- Out of scope: writing conversational statements to DB, long-term memory, note persistence from chat, statement-to-structured-data extraction

#### Trust-level prompt structure (per turn)

```
[system]
  You are a habit tracking assistant. Answer ONLY using the provided evidence.
  Conversation history shows what was said previously — treat it as context
  only, not as verified data. Do not invent facts not present in the evidence.

[user — window turn 1]  (prior)
  <message text>
[assistant — window turn 1]  (prior)
  <answer text>
...
[user — current turn]
  Evidence (verified, from database/search):
  <context_text>

  Conversation history (unverified, from this session):
  <recent N turns>

  Question: <current message>
```

**Not included:** DB writes from chat statements, persistent checkpointer, streaming

---

## Test Strategy

| Layer | What's tested | Mock boundary |
|-------|--------------|---------------|
| Node unit tests | Each node in isolation | `session`, providers mocked |
| Routing tests | `intent_router` for each intent value | Pure function, no mocks |
| Graph integration test | Full `graph.invoke(state)` round-trip | Providers mocked, real session |
| Endpoint tests | HTTP layer, guardrails, schema validation | `_graph.invoke` patched |
| Multi-turn tests | `messages` accumulates across turns; window cap enforced | MemorySaver, mocked provider |

---

## Out of Scope for Phase 06

- Long-term memory (Postgres checkpointer)
- Autonomous tool-calling agents
- Full clarify UX (field is scaffolded as placeholder only)
- Camera / YOLO features
- Streaming responses

---

## Decisions (locked)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Checkpointer: `MemorySaver`** for Rev 04 | Goal is proving LangGraph thread wiring, not persistence. Restarts clearing threads is acceptable for dev. Postgres-backed persitence deferred. |
| 2 | **Return `thread_id` in `ChatResponse`** | Frontend needs the server-assigned ID to continue a conversation thread. Server generates a UUID when the client omits it. |
| 3 | **Single `gather_context_node`** | Reuses `gather_context()` as-is. Splitting into two nodes adds wiring complexity for no behavioural benefit at this stage. |
| 4 | **Keep `handle_chat` in `chat_service.py`** | Stop calling it from the endpoint in Rev 05, but do not delete. Serves as migration reference until Phase 07 cleanup. |
