# Phase 04 Rev 03 — Embedding Pipeline (Production-Grade)

## Goal

Build an idempotent CLI pipeline that embeds all notes with `NULL` embeddings via a local Ollama server, using a clean layered architecture with full test coverage.

## Key Decisions

- **`EmbeddingProvider` ABC** — the pipeline depends on an abstract interface, not Ollama directly. This makes the provider swappable (OpenAI, HuggingFace, etc.) and all service logic independently testable with mocks.
- **Retry with exponential backoff on transient failures** — `OllamaProvider` retries on 5xx / connect errors up to `OLLAMA_MAX_RETRIES` times. 4xx errors fail immediately. This makes the pipeline resilient to Ollama restarts without masking real errors.
- **Per-note error isolation** — if one note fails to embed, the pipeline logs the error and continues with the next note. The `EmbedResult` tracks processed/skipped/error counts so the caller (or CI) can decide how to react.
- **Dimension validation before write** — vectors that don't match `EMBED_EXPECTED_DIMS` are rejected with a warning rather than silently corrupting the DB column.
- **Batch commits** — notes are committed in batches of `EMBED_BATCH_SIZE` (default 50) to balance memory usage and round-trip overhead.
- **All configuration via env vars** — no hardcoded values in any module. Settings centralised in `habittracker/core/config.py`.

## Architectural Context

```
make embed-notes
     │
     ▼
scripts/embed/main.py          ← thin entry point
     │
     ├─ scripts/embed/db.py    ← .env loading + DATABASE_URL + session factory
     │
     ├─ habittracker/providers/ollama.py  ← OllamaProvider (retry/backoff)
     │       implements
     │           habittracker/providers/base.py  ← EmbeddingProvider ABC
     │
     └─ habittracker/services/embedding_service.py  ← embed_notes() pipeline
                 │
                 └─ habittracker/models/repository/embedding_repository.py  ← SQL
```

**Package boundary rule:** `habittracker/` never imports from `scripts/`. `scripts/embed/` is a thin CLI runner that imports from `habittracker/` for all business logic.

## Scope Implemented

- `habittracker/core/config.py` — shared Ollama and pipeline settings (env vars)
- `habittracker/providers/base.py` — `EmbeddingProvider` ABC + `EmbeddingError`
- `habittracker/providers/ollama.py` — `OllamaProvider` with retry/backoff
- `habittracker/services/embedding_service.py` — `EmbedResult`, `embed_notes()`, batching, dim validation
- `habittracker/models/repository/embedding_repository.py` — `NoteRow`, `vector_to_literal`, `fetch_unembedded_notes`, `update_note_embedding`
- `scripts/embed/db.py` — .env loading, `DATABASE_URL`, engine, session factory
- `scripts/embed/main.py` — thin entry point with structured logging
- `Makefile` — `test-embed` target
- 36 tests across 4 test files (all passing):
  - `test_base.py` (5) — provider contract, error type
  - `test_ollama.py` (8) — success, missing key, 4xx, 5xx retry, connect retry
  - `test_repository.py` (11) — `vector_to_literal` (7), `fetch_unembedded_notes` (4, SQLite)
  - `test_service.py` (12) — batching, error isolation, dim validation, EmbedResult

## Files Changed

```
backend/habittracker/core/__init__.py
backend/habittracker/core/config.py
backend/habittracker/providers/__init__.py
backend/habittracker/providers/base.py
backend/habittracker/providers/ollama.py
backend/habittracker/services/__init__.py
backend/habittracker/services/embedding_service.py
backend/habittracker/models/repository/embedding_repository.py
backend/scripts/embed/__init__.py
backend/scripts/embed/db.py
backend/scripts/embed/main.py
backend/tests/__init__.py
backend/tests/scripts/__init__.py
backend/tests/scripts/embed/__init__.py
backend/tests/scripts/embed/test_base.py
backend/tests/scripts/embed/test_ollama.py
backend/tests/scripts/embed/test_repository.py
backend/tests/scripts/embed/test_service.py
backend/pyproject.toml (pytest, pytest-cov, httpx)
backend/poetry.lock
Makefile (test-embed target)
```

## Notes

- `embed-notes` smoke-tested: all seeded notes embedded successfully, re-run is idempotent ("No notes need embedding — nothing to do").
- `scripts/embed/` has only 3 files (`__init__.py`, `db.py`, `main.py`) — all logic lives in `habittracker/`.
- No LangChain dependency — plain `httpx` to Ollama's HTTP API.

## Next Step

Rev 04 — semantic search API endpoint (`GET /api/v1/search?q=&limit=`).
