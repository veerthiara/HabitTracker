# LangGraph + pgvector Project Plan (Step-by-Step)

This plan is organized by phases with clear deliverables so you can build incrementally and always have a runnable system.

## Real-time database strategy (choose one, or start with A then move to B)

### A) Self-populated local DB (recommended for learning)
- Run Postgres + pgvector locally in Docker.
- Ingest your own `.md` / `.txt` docs from `data/`.
- Best when you want to understand schema, ingestion, and retrieval deeply.

### B) Pre-populated DB (recommended for fast demos)
- Start from a seeded SQL dump or startup seed script.
- Optionally ship a small curated sample corpus in the repo.
- Best when you want to focus on agent behavior and UI quickly.

## Phase 01 — Repo bootstrap (backend + UI skeleton)

**Deliverable:** `docker compose up` works, backend runs, UI runs, health endpoint is available.

**Scope**
- `backend/` FastAPI app with `/health`
- `frontend/` Vite React app with basic page
- `docker-compose.yml` (DB only for now or DB + backend)
- Optional `Makefile` or `justfile`
- Root `README.md` with dev commands

**Copilot prompt**
> Create a monorepo with backend (FastAPI) and frontend (Vite React). Add a root README with commands to run both. Add /health endpoint. Keep it minimal.

## Phase 02 — Local Postgres + pgvector

**Deliverable:** DB runs locally; migrations create vector schema; quick verification script succeeds.

**Scope**
- Add Postgres container with `pgvector` enabled
- Use Alembic (or SQL migrations) to create schema:
	- `documents(id, source, content, metadata jsonb, embedding vector)`
	- Optional `chunks` table for chunk-level retrieval
- Add a quick verify script or endpoint for insert/select

**Copilot prompt**
> Add docker-compose Postgres with pgvector. Add migration creating documents/chunks schema. Provide a quick python script or endpoint to verify insert/select.

## Phase 03 — Ingestion pipeline

**Deliverable:** `python -m backend.ingest` loads sample docs, chunks, embeds, and stores without duplicates.

**Scope**
- Load files from `data/` (`.md`, `.txt` initially)
- Use simple recursive text splitter
- Embed and upsert into Postgres
- Add deterministic IDs (hash of `source + content`) for rerunnable ingestion
- Add minimal logging

**Copilot prompt**
> Implement ingestion: read data/ docs, chunk, embed, store in Postgres pgvector. Make it re-runnable without duplicates. Add README instructions.

## Phase 04 — RAG API in FastAPI

**Deliverable:** `/chat` endpoint performs retrieval + generation and returns answer with sources.

**Scope**
- Build retriever against pgvector
- Chain flow:
	- embed query
	- similarity search (`top-k`)
	- prompt with context
	- generate response
- Return payload:
	- `answer`
	- `sources` (chunk ID, source, snippet)

**Copilot prompt**
> Add /chat endpoint that runs RAG against pgvector chunks and returns answer + sources. Include curl example and a basic test.

## Phase 05 — LangGraph orchestration (agent backend)

**Deliverable:** RAG logic is handled by a LangGraph agent with routing, retrieval, generation, citations, and short thread memory.

**Graph design**
- **State**: `{messages, query, retrieved_docs, answer, thread_id}`
- **Nodes**:
	- `route` → decide retrieve vs direct answer
	- `retrieve` → vector search
	- `generate` → answer with citations
	- `clarify` (optional) → ask follow-up when context is insufficient

**Scope**
- Keep API contract stable (`/chat` request/response)
- Add `thread_id` support for short conversation memory
- Keep citations in response format

**Copilot prompt**
> Refactor the RAG logic into LangGraph with nodes: route, retrieve, generate, (optional clarify). Keep API contract stable. Add a thread_id to maintain short memory.

## Phase 06 — React UI (chat + document lookup)

**Deliverable:** UI chats with backend, displays citations, and supports doc lookup.

**Scope**
- Chat panel:
	- messages
	- expandable `sources`
- Lookup panel:
	- query endpoint `/docs?q=...`
	- list docs + preview

**Copilot prompt**
> Build a minimal React UI with chat and sources display, calling /chat. Add a lookup page calling /docs. Keep styling minimal.

## Phase 07 — End-to-end polish

**Deliverable:** Demo-ready app with one-command startup and basic quality checks.

**Scope**
- Seed data + one command to run everything
- Add eval script (few queries + expected source presence)
- Add basic observability (request logs, latency)
- Add guardrails:
	- If no sources, answer with “I don’t know”
	- cap `top-k`, token limits, and timeout bounds

## Suggested execution order for your goal (LangGraph first + real-time DB)

1. Complete Phases 01 and 02.
2. Decide DB mode:
	 - **Learning mode:** self-ingest (Phase 03)
	 - **Demo mode:** pre-populated seed (Phase 07 seed task moved earlier)
3. Implement `/chat` baseline (Phase 04).
4. Move to LangGraph orchestration (Phase 05).
5. Add UI integration (Phase 06).