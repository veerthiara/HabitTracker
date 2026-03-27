# Phase 04 — pgvector Layer (Revised Plan)

## Rev 01 — Enable pgvector in Postgres

Add pgvector for semantic search use cases.

### Scope:

- Swap Docker image in docker-compose.yml: postgres:16 → pgvector/pgvector:pg16
- Add pgvector Python package to pyproject.toml
- New Alembic migration 0002_enable_pgvector.py: CREATE EXTENSION IF NOT EXISTS vector
- Add make local-db-reset Makefile target (down -v + up -d) for convenience
- Add make embed-notes placeholder stub to Makefile (used in Rev 03)
⚠️ DB volume must be recreated (pgvector image replaces plain postgres).

Run in order after the image is swapped:

```bash
make local-db-down         # stop containers
docker volume rm <pg_data_volume>   # or: docker compose down -v
make local-db-up           # start fresh with pgvector image
make db-migrate            # runs 0001_initial + 0002_enable_pgvector
make db-seed               # re-seeds all demo data
```

## Rev 02 — Embedding column on notes (ORM + migration)
### Scope:
- Add embedding column to Note ORM model — type Vector from pgvector.sqlalchemy, dimension driven by EMBED_DIMS env var (default 768), nullable (non-breaking)
- New Alembic migration 0003_note_embeddings.py:
  - Adds embedding vector(768) column (nullable)
  - Adds HNSW index: CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)
- No DB recreation — additive migration only, run make db-migrate
- Embedding dimension is only configured at migration time; if you change models later, a new migration adds a new column or replaces it, rather than hardcoding 768 everywhere in application code
- NoteRead schema in schemas/note.py is not changed — embedding stays internal, never serialised to API consumers

## Rev 03 — Embedding pipeline (scripts)

### Scope:
- New backend/scripts/embed/ folder (parallel to seed/):
    - __init__.py
    - ollama_client.py — thin HTTP wrapper around http://localhost:11434/api/embeddings, model and base URL read from env vars (OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL), returns list[float]
    - main.py — queries notes WHERE embedding IS NULL, calls ollama_client, writes vector back, commits per batch of 50
- Idempotent by design — WHERE embedding IS NULL means re-running is always safe
- backend/.env additions (gitignored): OLLAMA_BASE_URL=http://localhost:11434, OLLAMA_EMBED_MODEL=nomic-embed-text
- make embed-notes Makefile target (replaces stub from Rev 01)
- No new API endpoints — pipeline is CLI-only
- No LangChain dependency — plain httpx or urllib call to Ollama's HTTP API
- No DB recreation — run make embed-notes after Rev 02 migration

## Rev 04 — Semantic search API
### Scope:

- New backend/habittracker/models/repository/search_repository.py:
    - search_notes(session, query_vec, limit) → list[NoteSearchHit]
    - Uses pgvector <=> cosine distance operator
    - Returns (id, content, score) — no embedding arrays
- New backend/habittracker/schemas/search.py:
    - NoteSearchHit — id: UUID, content: str, score: float (snippet truncated to 300 chars)
    - SearchResponse — query: str, results: list[NoteSearchHit]
- New backend/habittracker/api/v1/search.py:
    - GET /api/v1/search?q=&limit=5
    - Embeds query inline via same Ollama client from scripts/embed/ollama_client.py
    - Returns SearchResponse — business data only, no vectors exposed
- Wire router in server.py
- No DB recreation — make db-migrate is a no-op (no new migration needed)


## Constraints satisfied
| Constraint	| Where addressed |
|----------------|----------------|
| No fixed embedding dim in app code	| Dim only appears in the migration SQL; app code uses the column generically |
| Embeddings never in API responses	| NoteRead unchanged; NoteSearchHit returns only id, content, score |
| Pipeline is idempotent	| WHERE embedding IS NULL filter in Rev 03 main.py |
| Search returns business data	| SearchResponse has no vector fields |
| Backend-only, no LangChain	| Plain httpx to Ollama HTTP API |
| No breaking migrations	| Rev 02 column is nullable; Rev 01 is the only destructive step |