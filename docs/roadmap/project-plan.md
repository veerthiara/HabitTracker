---
title: Master Project Plan
sidebar_position: 1
---

# LangGraph + pgvector Project Plan

This is the book-style version of the root `ProjectPlan.md` so it can be read directly in the docs site.

## Real-time database strategy

### A) Self-populated local DB

- Run Postgres + pgvector locally in Docker
- Ingest your own `.md` and `.txt` docs
- Best when you want to understand schema, ingestion, and retrieval deeply

### B) Pre-populated DB

- Start from a seeded SQL dump or startup seed script
- Optionally ship a curated sample corpus in the repo
- Best when you want to focus on agent behavior and UI quickly

## Phase 01

**Deliverable:** `docker compose up` works, backend runs, UI runs, and the health endpoint is available.

- Backend: FastAPI app with `/health`
- Frontend: Vite React app with a basic page
- Root `docker-compose.yml`
- Optional `Makefile`
- Root README with dev commands

## Phase 02

**Deliverable:** DB runs locally, migrations create vector schema, and quick verification succeeds.

- Add Postgres container with `pgvector`
- Create schema for documents and chunks
- Add a small verify script or endpoint

## Phase 03

**Deliverable:** ingestion loads sample docs, chunks, embeds, and stores without duplicates.

- Read docs from local files
- Split content into chunks
- Embed and upsert into Postgres
- Use deterministic IDs for reruns
- Add minimal logging

## Phase 04

**Deliverable:** `/chat` performs retrieval plus generation and returns an answer with sources.

- Embed query
- Run similarity search
- Prompt with retrieved context
- Return `answer` and `sources`

## Phase 05

**Deliverable:** LangGraph handles routing, retrieval, generation, citations, and short memory.

- Keep the `/chat` API contract stable
- Add `thread_id`
- Support direct answer vs retrieval routing

## Phase 06

**Deliverable:** the React UI supports chat and document lookup.

- Chat panel with messages and sources
- Lookup panel for docs and previews

## Phase 07

**Deliverable:** demo-ready app with one-command startup and basic quality checks.

- Seed data
- Add eval coverage
- Add request logging and latency visibility
- Add guardrails and limits

## Suggested execution order

1. Finish Phases 01 and 02
2. Choose learning mode or demo mode for the DB
3. Implement `/chat`
4. Move to LangGraph orchestration
5. Add UI integration
