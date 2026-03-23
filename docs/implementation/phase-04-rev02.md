# Phase 04 Rev 02 — Embedding Column on Notes

## Goal

Add a `vector(768)` embedding column to the `notes` table with an HNSW index for cosine similarity search.

## Key Decisions

- **Dimension (768) co-located with the model choice** — `nomic-embed-text` always produces 768-dim vectors. The constant `EMBED_DIMS = 768` lives in the Note ORM model next to the column definition so the coupling between model and schema is explicit.
- **HNSW index with `vector_cosine_ops`** — HNSW gives approximate nearest-neighbor search with sub-linear query time. `m=16, ef_construction=64` are pgvector defaults and sufficient for a local dataset of thousands of notes.
- **Migration uses raw DDL (`op.execute`)** — avoids importing pgvector's SQLAlchemy types into the Alembic env, which would pull in numpy and other dependencies at migration time.
- **Column is nullable** — existing rows get `NULL` embedding. The embedding pipeline (Rev 03) fills them in. This keeps the migration additive and non-breaking.
- **`NoteRead` schema unchanged** — embeddings are internal; they are never serialised to API consumers.

## Architectural Context

```
notes table
├── id, user_id, content, created_at, updated_at   (from 0001_initial)
└── embedding vector(768)                           (this migration)
         ↑
    HNSW index (vector_cosine_ops)
         ↑
    Populated by scripts/embed/ pipeline (Rev 03)
    Queried by search API (Rev 04)
```

## Scope Implemented

- `backend/habittracker/models/orm/habittracker/note.py` — added `embedding: Mapped[Vector(768)]`, nullable, `EMBED_DIMS = 768`
- `backend/alembic/versions/0003_note_embeddings.py` — `ALTER TABLE notes ADD COLUMN embedding vector(768)` + HNSW index

## Files Changed

```
backend/habittracker/models/orm/habittracker/note.py
backend/alembic/versions/0003_note_embeddings.py
```

## Notes

- No DB volume teardown needed — this is a pure additive migration (`make db-migrate`).
- All existing seeded notes have `embedding IS NULL` after migration — expected.
- If the embedding model changes in the future, a new migration adds/replaces the column with the new dimension.

## Next Step

Rev 03 — embedding pipeline (`scripts/embed/`) to populate NULL embeddings via Ollama.
