# Phase 04 Rev 04 — Semantic Search API

## Goal

Expose a `GET /api/v1/search?q=<query>&limit=<n>` endpoint that embeds the user's query via Ollama and returns the most similar notes using pgvector cosine distance.

## Key Decisions

- **Inline query embedding** — the query is embedded on the request path using the same `OllamaProvider` from Rev 03. Acceptable for local/dev use; a caching layer or dedicated embedding service would be added for production latency requirements.
- **Single shared `OllamaProvider` instance** — reuses one `httpx.Client` across all requests to avoid connection churn. Instantiated at module level in the search router.
- **Vectors never returned to the caller** — `SearchResponse` contains `id`, `snippet` (truncated to 300 chars), and `score` only. Embeddings are an internal implementation detail.
- **`1 - cosine_distance` as score** — pgvector's `<=>` operator returns distance (lower = closer). The API returns `1 - distance` so higher scores mean more similar, which is more intuitive for consumers.
- **`search_service.py` as a thin helper** — `embed_query()` wraps the provider call so the API layer depends on the `EmbeddingProvider` abstraction rather than constructing vectors directly.

## Architectural Context

```
GET /api/v1/search?q=water&limit=3
         │
         ▼
  api/v1/search.py
    ├─ embed query → habittracker/providers/ollama.py
    │                     ↓
    │              habittracker/core/config.py (settings)
    │
    └─ search DB  → habittracker/models/repository/search_repository.py
                          ↓
                    pgvector <=> cosine distance on notes.embedding
                          ↓
                    SearchResponse (id, snippet, score)
```

## Scope Implemented

- `habittracker/schemas/search.py` — `NoteSearchHit` (id, snippet, score), `SearchResponse` (query, total, results)
- `habittracker/models/repository/search_repository.py` — `NoteSearchRow`, `search_notes()` using `<=>` operator, user-scoped, excludes un-embedded notes
- `habittracker/api/v1/search.py` — `GET /api/v1/search/` route with query validation (`min_length=1, max_length=500`, `limit 1–20`)
- `habittracker/services/search_service.py` — `embed_query()` helper
- `habittracker/server.py` — wired search router

## Files Changed

```
backend/habittracker/schemas/search.py
backend/habittracker/models/repository/search_repository.py
backend/habittracker/api/v1/search.py
backend/habittracker/services/search_service.py
backend/habittracker/server.py
```

## Notes

- Smoke-tested: `curl "http://127.0.0.1:8000/api/v1/search/?q=water&limit=3"` returns ranked results from seeded notes.
- Notes without embeddings are silently excluded — run `make embed-notes` before searching.
- No new migration needed — this revision only reads the existing `embedding` column.
- 36/36 existing tests still passing.

## Next Step

Phase 05 — AI chat interface (LangChain/LangGraph integration).
