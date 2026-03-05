# Copilot Prompts

## General repo rule
This project is a product-first habit tracker, not a docs-RAG demo.
Prefer structured application design first:
- FastAPI backend
- React frontend
- Postgres source of truth
- pgvector only for semantic AI features
- LangGraph only when multi-step AI orchestration is needed
- future camera/YOLO service must remain separate from core backend

## Phase 01
Create a monorepo with frontend (React + Vite) and backend (FastAPI). Add a /health endpoint and minimal startup instructions.

## Phase 02
Add Postgres and migrations for users, habits, habit_logs, bottle_events, notes, and daily_summaries.

## Phase 03
Build APIs and minimal UI for manual habit logging, bottle event logging, and dashboard summaries.

## Phase 04
Enable pgvector and add note embeddings plus semantic retrieval support.

## Phase 05
Add a /chat endpoint for natural-language analytics over structured habit data.

## Phase 06
Refactor the AI flow into LangGraph with thread_id support and routing between analytics and retrieval.

## Phase 08
Create a separate vision service scaffold for future camera and YOLO-based event generation.