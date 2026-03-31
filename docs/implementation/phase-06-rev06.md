# Phase 06 Rev 06 — Multi-Turn Conversation Memory

## Goal

Extend the LangGraph chat pipeline with a windowed conversation history so that follow-up questions within a thread are handled correctly. The LLM now receives prior user/assistant turns alongside the current evidence, allowing it to recall what was said earlier in the same session.

## Key Decisions

**1. Keep both `message` (current turn input) and `messages` (accumulated history).**
`message` stays as the raw input field populated by the endpoint. `messages` is a separate accumulation field that grows across turns. Nodes never replace `message` — they append to `messages`. This keeps the per-turn intent classification and evidence lookup clean (they operate on `state["message"]`), while the LLM gets the full picture via `messages`.

**2. `ConversationTurn` TypedDict instead of raw dicts.**
`messages` holds `list[ConversationTurn]` (a simple TypedDict with `role: str` and `content: str`). This avoids untyped `dict` flowing through nodes and makes shape errors catchable at the test level. The TypedDict is thin enough to remain msgpack-serialisable by MemorySaver.

**3. LangGraph `operator.add` reducer for `messages`.**
Annotating `messages: Annotated[list[ConversationTurn], operator.add]` tells LangGraph to *concatenate* any list returned by a node onto the checkpoint's existing list, rather than replace it. This is the standard LangGraph pattern for accumulating state across turns.

**4. `CONVERSATION_WINDOW = 10` cap enforced before the LLM call.**
The full history is stored in the checkpoint (unlimited). Before building the LLM payload, the node slices `prior_turns[-CONVERSATION_WINDOW:]`. This keeps prompt size bounded while the checkpoint remains a complete record.

**5. Three explicit trust levels in every LLM call.**
- `system` role: who the assistant is + trust rules (unchanged from Rev 05)
- Prior conversation turns: sent verbatim as `user`/`assistant` roles so the model has the natural back-and-forth
- Current `user` turn content: two labeled sections — "Evidence (verified, from database/search)" and "Conversation history (unverified — from this session only, not confirmed by database)"

This separation prevents the model from treating a user statement like "I drank 8 glasses" as confirmed DB data when answering questions like "Was that more than yesterday?".

**6. `ChatProvider.complete()` signature upgraded from `(system, user)` to `(messages: list[dict])`.**
The multi-turn prompt is a list of dicts. The old two-string signature cannot represent a multi-turn history. The abstract base class is updated; `OllamaChatProvider` forwards the list to Ollama's `/api/chat` (which already accepts multi-turn natively). User-visible interface is unchanged.

**7. `classify_intent_node` appends the user turn; `generate_answer_node` appends the assistant turn.**
The user turn is appended at classification time (before routing) so it enters history regardless of whether the UNSUPPORTED shortcut is taken. The assistant turn (including the fallback answer) is always appended at generation time.

## Architectural Context

```
ChatRequest  →  classify_intent_node
                     │
                     ├─ appends user ConversationTurn to messages[]
                     │
                     ▼ (route)
           gather_context_node (supported intents only)
                     │
                     ▼
           generate_answer_node
                     │
                     ├─ reads state["messages"][:-1] as prior history
                     ├─ applies CONVERSATION_WINDOW slice
                     ├─ builds:
                     │    [system] SYSTEM_PROMPT
                     │    [user/assistant] windowed prior turns
                     │    [user] Evidence (verified) + History (unverified) + Question
                     ├─ calls chat_provider.complete(payload)
                     └─ appends assistant ConversationTurn to messages[]
```

MemorySaver uses `operator.add` to merge `messages` across checkpoint turns — old messages are never lost from the persisted state, only windowed for the LLM prompt.

## Scope Implemented

- `habittracker/graph/state.py` — added `ConversationTurn` TypedDict, `CONVERSATION_WINDOW = 10` constant, `messages: Annotated[list[ConversationTurn], operator.add]` field; imports `operator`, `Annotated`
- `habittracker/graph/nodes.py` — `classify_intent_node` appends user turn to `messages`; `generate_answer_node` builds windowed multi-turn payload with trust-level labeling, appends assistant turn; fallback path also appends assistant turn
- `habittracker/providers/base.py` — `ChatProvider.complete()` signature changed from `(system: str, user: str)` to `(messages: list[dict])`
- `habittracker/providers/ollama_chat.py` — `complete()` accepts `list[dict]`, forwards it directly to Ollama `/api/chat`; no more inline `messages` construction in the provider
- `tests/habittracker/graph/test_nodes.py` — classify_intent tests assert `messages` field; generate_answer tests use new `messages`-list `complete()` signature; new tests for trust-level labeling, window cap, assistant-turn append
- `tests/habittracker/providers/test_ollama_chat.py` — all calls updated to `complete(list[dict])`; added `test_multi_turn_payload_passed_verbatim`
- `tests/habittracker/graph/test_multiturn_memory.py` — new file: 20 tests covering single-turn accumulation, multi-turn growth, thread isolation, window cap, trust-level labeling
- `docs/roadmap/phase-06-langgraph-detailed.md` — Rev 06 section added

## Files Changed

```
habittracker/graph/state.py
habittracker/graph/nodes.py
habittracker/providers/base.py
habittracker/providers/ollama_chat.py
tests/habittracker/graph/test_nodes.py
tests/habittracker/providers/test_ollama_chat.py
tests/habittracker/graph/test_multiturn_memory.py   ← new
docs/roadmap/phase-06-langgraph-detailed.md
docs/implementation/phase-06-rev06.md
```

## Notes

- 217 tests pass (up from 194 in Rev 05; 23 new tests).
- `handle_chat` in `chat_service.py` still passes `complete(SYSTEM_PROMPT, user_prompt)` — it is dead code (not called from endpoint since Rev 05) and its internal signature is not updated. If it is ever reinstated it will need updating.
- The "8 glasses of water" scenario now works within a session: Turn 1's user message is in `messages`; Turn 2's LLM payload includes it as prior conversation history, correctly labeled as unverified.
- Statements made in chat still do not write to the database. The model can *recall* them from session history, but cannot answer DB-grounded follow-ups like "Was that more than yesterday?" from that statement alone.

## Next Step

Phase 07 — UI polish: connect React frontend to the live graph endpoint, display `evidence` cards, thread continuity via `thread_id`, show `used_notes` badge.
