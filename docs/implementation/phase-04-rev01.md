# Phase 04 Rev 01 — Enable pgvector in Postgres

## Goal

Add pgvector extension support to the local Postgres instance so that future revisions can store and query embedding vectors.

## Key Decisions

- **Swap the Docker image (`postgres:16` → `pgvector/pgvector:pg16`)** rather than compiling the extension inside the existing image. The official pgvector image is maintained upstream and tracks Postgres releases — less maintenance for us.
- **Extension enabled via Alembic migration (`0002_enable_pgvector`)** instead of an init SQL script. This keeps all schema changes in the migration chain and makes it obvious when the extension was introduced.
- **`make local-db-reset` target added** — swapping images requires a volume teardown. A single command (`make local-db-reset`) does `down -v` + `up -d` + `db-migrate` + `db-seed` so the developer workflow stays simple.
- **`make embed-notes` added as a stub** — wired to a no-op so the target exists for Rev 03 without breaking anything now.

## Architectural Context

pgvector is a foundational dependency for all semantic features (note search, habit recommendations, AI chat context). By enabling the extension at the infrastructure level first, subsequent revisions can add embedding columns and queries without touching infra again.

```
infra/local/docker-compose.yml   ← image swap
        ↓
  0001_initial.py → 0002_enable_pgvector.py
                         CREATE EXTENSION IF NOT EXISTS vector
```

## Scope Implemented

- `infra/local/docker-compose.yml` — image `pgvector/pgvector:pg16`
- `backend/alembic/versions/0002_enable_pgvector.py` — `CREATE EXTENSION IF NOT EXISTS vector`
- `backend/pyproject.toml` — added `pgvector ^0.3`
- `Makefile` — `local-db-reset`, `embed-notes` stub
- `docs/roadmap/phase-04-pgvector-detailed.md` — detailed plan for Rev 01–04

## Files Changed

```
infra/local/docker-compose.yml
backend/alembic/versions/0002_enable_pgvector.py
backend/pyproject.toml
backend/poetry.lock
Makefile
docs/roadmap/phase-04-pgvector-detailed.md
```

## Notes

- DB volume must be recreated when moving from plain `postgres:16` to `pgvector/pgvector:pg16`. `make local-db-reset` handles this.
- pgvector 0.8.2 verified running inside the container after migration.
- No application code changes — this revision is purely infrastructure.

## Next Step

Rev 02 — add `embedding vector(768)` column to the notes table with an HNSW index.
