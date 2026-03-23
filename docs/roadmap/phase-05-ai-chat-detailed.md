# Phase 05 — AI Chat over Habit Data (Detailed Plan)

## Goal

Add a `POST /api/v1/chat` endpoint that answers natural-language questions
about habits, hydration, and notes — grounded in real data, not hallucination.

The system must:

* prioritize structured analytics (SQL-backed data) over fuzzy search
* use semantic note retrieval (pgvector) only for pattern/explanation questions
* return evidence-backed answers so the UI can show *what* the answer is based on
* fail safe when data is insufficient ("I don't have enough data")

---

## Key Design Principles

### 1. Analytics-first, not RAG-first

SQL data is accurate and deterministic. Embeddings are approximate.
Use structured repos as the *primary* source of truth.
Use pgvector note search *only* when the intent specifically requires it.

### 2. Backend-only — no LangChain / no LangGraph

All logic stays inside `habittracker/`. Plain `httpx` calls to Ollama.
LangGraph orchestration is deferred to Phase 06.

### 3. Deterministic routing before LLM

1. Classify intent (rule-based, no LLM)
2. Fetch relevant data from the right repo
3. Build a constrained prompt
4. Call LLM for natural-language generation only

### 4. Evidence-driven responses

Every answer must be backed by `EvidenceItem` objects.
If no evidence can be gathered → return a safe fallback, never hallucinate.

### 5. Explicit search-usage rule

| Intent | Data source | Semantic search? |
|--------|------------|-----------------|
| `habit_summary` | habit_repository, habit_log_repository | NO |
| `bottle_activity` | bottle_event_repository | NO |
| `note_pattern_question` | search_repository (pgvector) | YES |
| `general_question` | dashboard_repository + search_repository | YES (fallback) |
| `unsupported` | none | NO |

Rule: **never mix fuzzy vector results into count/time-based queries.**
Semantic search is reserved for pattern, explanation, and open-ended questions.

---

## LLM Model

**Chat model:** `llama3.2` (3B, already pulled locally)
Endpoint: Ollama `/api/chat` — structured message format (system + user).

> If response quality is insufficient during smoke-testing, we can swap to a
> larger model (e.g. `mistral`, `phi3`) via the `OLLAMA_CHAT_MODEL` env var
> with zero code changes.

**Embedding model:** `nomic-embed-text` (768 dims) — already in use from Phase 04.

---

## API Contract

### Endpoint

`POST /api/v1/chat`

### Request

```json
{
  "message": "How many times did I pick up my bottle today?"
}
```

* `message` — required, 1–500 chars
* No `user_id` in body — uses `get_current_user_id()` dependency (same as all other endpoints)
* No `include_notes` toggle — the system decides based on intent classification

### Response

```json
{
  "answer": "You picked up your bottle 6 times today, totalling 1800 ml.",
  "intent": "bottle_activity",
  "used_notes": false,
  "evidence": [
    {
      "type": "metric",
      "label": "Bottle pickups today",
      "value": "6"
    },
    {
      "type": "metric",
      "label": "Total hydration",
      "value": "1800 ml"
    }
  ]
}
```

### Response (with note retrieval)

```json
{
  "answer": "You tend to miss your water goal on days where your notes mention fatigue or late meetings.",
  "intent": "note_pattern_question",
  "used_notes": true,
  "evidence": [
    {
      "type": "note",
      "label": "2026-03-18",
      "value": "Felt tired after lunch and forgot bottle"
    },
    {
      "type": "note",
      "label": "2026-03-20",
      "value": "Late meeting broke my routine"
    }
  ]
}
```

### Response (insufficient data)

```json
{
  "answer": "I don't have enough data to answer that.",
  "intent": "unsupported",
  "used_notes": false,
  "evidence": []
}
```

---

## Folder Structure Additions

```text
habittracker/
  core/
    config.py              ← add OLLAMA_CHAT_MODEL, OLLAMA_CHAT_TIMEOUT_SEC
  providers/
    base.py                ← add ChatProvider ABC alongside EmbeddingProvider
    ollama_chat.py         ← new: OllamaChatProvider (calls /api/chat)
  schemas/
    chat.py                ← new: ChatRequest, ChatResponse, EvidenceItem
  services/
    chat_intent_service.py ← new: classify_intent()
    chat_data_service.py   ← new: gather_evidence() → evidence + context_text + used_notes
    chat_service.py        ← new: orchestrator (intent → data → prompt → LLM → response)
  api/
    v1/
      chat.py              ← new: POST /api/v1/chat
```

---

## Phase Breakdown (4 Revisions)

---

### Rev 01 — Chat Provider + Schemas

#### Scope

* **Config:** add `OLLAMA_CHAT_MODEL` (default: `llama3.2`), `OLLAMA_CHAT_TIMEOUT_SEC` (default: `120`) to `core/config.py`
* **Provider ABC:** add `ChatProvider` to `providers/base.py`
  * `complete(system: str, user: str) → str`
  * `ChatCompletionError(RuntimeError)`
* **Ollama chat provider:** `providers/ollama_chat.py` — `OllamaChatProvider`
  * Calls `/api/chat` with `{"model": ..., "messages": [...], "stream": false}`
  * Retry with exponential backoff on 5xx / connect errors (same pattern as `OllamaProvider`)
  * Non-retryable on 4xx
  * Timeout handling: if Ollama exceeds `OLLAMA_CHAT_TIMEOUT_SEC` → raise `ChatCompletionError`
* **Schemas:** `schemas/chat.py`
  * `ChatRequest` — `message: str` (min 1, max 500)
  * `EvidenceItem` — `type: str`, `label: str`, `value: str`
  * `ChatResponse` — `answer: str`, `intent: str`, `used_notes: bool`, `evidence: list[EvidenceItem]`
* **Tests:** mock httpx tests for `OllamaChatProvider` (success, 4xx, 5xx retry, timeout, missing key)

#### Deliverable

Working LLM call + stable API contract. Everything else builds on this.

---

### Rev 02 — Intent Classification + Data Gathering

#### Scope

##### Intent classification (`services/chat_intent_service.py`)

* Rule-based keyword/pattern matching — no LLM needed
* Intents:

| Intent | Trigger patterns |
|--------|-----------------|
| `habit_summary` | "habit", "how many habits", "what habits", "my habits" |
| `bottle_activity` | "bottle", "water", "hydration", "drink" |
| `note_pattern_question` | "why", "pattern", "trend", "reason", "notice" |
| `general_question` | anything that doesn't match above |
| `unsupported` | greetings, off-topic, empty-ish |

* **Fallback strategy:** if no keyword matches → classify as `general_question`
  (not `unsupported`). Only classify as `unsupported` for clearly off-topic input
  (greetings, gibberish). This prevents over-rejecting legitimate questions that
  just use unexpected wording.

##### Data gathering (`services/chat_data_service.py`)

* `gather_evidence(session, user_id, intent, message) → ChatDataResult`
* Returns a structured result:

```python
@dataclass
class ChatDataResult:
    evidence: list[EvidenceItem]   # structured facts for the response
    context_text: str              # prompt-ready text for the LLM
    used_notes: bool               # whether semantic search was used
```

* Per-intent data sources (composes from **existing repositories** — no new SQL):

| Intent | Repos used | Semantic search? |
|--------|-----------|-----------------|
| `habit_summary` | `habit_repository`, `habit_log_repository`, `dashboard_repository` | NO |
| `bottle_activity` | `bottle_event_repository`, `dashboard_repository` | NO |
| `note_pattern_question` | `search_repository` (pgvector) | YES (max 5 notes) |
| `general_question` | `dashboard_repository` + `search_repository` (fallback) | YES (max 3 notes) |
| `unsupported` | none | NO |

* **Tests:**
  * Intent classification: pure function tests, no DB, no mocks — just input → intent
  * Data gathering: mocked session, verify correct repos are called per intent

#### Deliverable

System can classify any message and gather the right evidence without an LLM.

---

### Rev 03 — Prompt Building + LLM Answer Generation

#### Scope

##### Chat orchestrator (`services/chat_service.py`)

Full pipeline:

1. `classify_intent(message)` → intent
2. `gather_evidence(session, user_id, intent, message)` → `ChatDataResult`
3. Build constrained prompt
4. Call `OllamaChatProvider.complete(system, user)` → answer text
5. Return `ChatResponse`

##### Prompt design

**System prompt:**

```
You are a habit tracking assistant. You help users understand their habits,
hydration, and notes.

Rules:
- Answer ONLY using the data provided below.
- Do NOT invent or assume any data not listed.
- If the data does not fully answer the question, say:
  "I don't have enough data to answer that."
- Keep answers concise (2-3 sentences max).
- Do not repeat the raw data back verbatim — summarize it naturally.
```

**User prompt:**

```
Data:
{context_text from ChatDataResult}

Question: {user's original message}
```

##### No-evidence shortcut

If `gather_evidence` returns an empty evidence list → skip the LLM call entirely
and return the safe fallback:

```json
{
  "answer": "I don't have enough data to answer that.",
  "intent": "...",
  "used_notes": false,
  "evidence": []
}
```

* **Tests:** full orchestration with mocked provider + mocked session. Verify:
  * Correct intent flows to correct data gathering
  * Empty evidence → fallback (no LLM call)
  * LLM response is returned in ChatResponse
  * `used_notes` flag propagated correctly

#### Deliverable

End-to-end pipeline: message → intent → data → prompt → LLM → response.

---

### Rev 04 — Chat Endpoint + Guardrails + Tests

#### Scope

##### Endpoint (`api/v1/chat.py`)

* `POST /api/v1/chat` → `ChatResponse`
* Uses `get_current_user_id()` dependency (same as all other endpoints)
* Wire router in `server.py`

##### Guardrails

| Guard | Behaviour |
|-------|-----------|
| No evidence | Skip LLM, return safe fallback |
| Note retrieval cap | Max 5 notes from semantic search |
| Response length cap | Truncate LLM output to 1000 chars |
| Ollama timeout | `ChatCompletionError` → HTTP 503 with helpful message |
| Ollama down | `ChatCompletionError` → HTTP 503 |
| Unsupported intent | Return fallback without calling LLM |

##### Smoke test

```bash
# Structured query (no notes)
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How much water did I drink today?"}'

# Pattern query (uses notes)
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Why do I keep missing my habits?"}'

# Unsupported
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

##### Implementation docs

* `docs/implementation/phase-05-rev01.md` through `phase-05-rev04.md`

#### Deliverable

Working, guardrailed, tested, demo-ready `/api/v1/chat` endpoint.

---

## Out of Scope (deferred to later phases)

| Feature | Phase |
|---------|-------|
| LangGraph agent orchestration | Phase 06 |
| Multi-turn memory / thread_id | Phase 06 |
| Autonomous tool calling | Phase 06 |
| Streaming responses | Phase 06 or 07 |
| Chat UI | Phase 07 |
| Camera / vision integration | Phase 08 |
| Streak calculation | Future (no current repo support) |

---

## Existing Code Reused

| Module | Used in |
|--------|---------|
| `providers/base.py` (EmbeddingProvider) | Rev 02 — note search embedding |
| `providers/ollama.py` (OllamaProvider) | Rev 02 — embed query for note search |
| `services/search_service.py` (embed_query) | Rev 02 — semantic note retrieval |
| `models/repository/search_repository.py` | Rev 02 — pgvector cosine search |
| `models/repository/dashboard_repository.py` | Rev 02 — habit/hydration summaries |
| `models/repository/habit_repository.py` | Rev 02 — habit list |
| `models/repository/habit_log_repository.py` | Rev 02 — habit completion data |
| `models/repository/bottle_event_repository.py` | Rev 02 — hydration events |
| `core/config.py` | Rev 01 — add chat model settings |
| `api/deps.py` (get_current_user_id) | Rev 04 — auth dependency |

---

## Design Notes

### Why structured-first, not RAG-first

* SQL data is deterministic — "how much water today?" has one correct answer
* Embedding similarity is approximate — useful for "why" questions, harmful for counts
* Constraining the LLM to provided evidence prevents hallucination
* The `used_notes` flag lets downstream consumers (UI, LangGraph) know the confidence level

### Why `ChatDataResult` carries both evidence + context_text

* `evidence` is machine-readable — the API consumer can render it in UI cards
* `context_text` is the prompt-ready string — the LLM needs a flat text block, not JSON
* `used_notes` signals whether fuzzy data was involved — important for Phase 06/07
* Keeping both in one return value avoids re-computing or losing track of what was used

