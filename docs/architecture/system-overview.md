# System Overview

## Goal
Build a local-first habit tracker focused on bottle pickup tracking, habit logging, dashboard analytics, and later camera-based event detection.

## Main parts
- Frontend: React app for dashboard, logging, and chat
- Backend: FastAPI for APIs, business logic, and AI endpoints
- Database: Postgres as source of truth
- Vector store: pgvector inside Postgres for embeddings
- AI orchestration: LangGraph for multi-step AI flows
- Future vision service: separate local service for camera/YOLO-based event detection

## Product direction
The app is product-first, not RAG-first.
The main data is structured application data:
- habits
- habit logs
- bottle events
- notes
Later, AI and vision features will build on top of this data.

## Initial MVP
- manual habit logging
- bottle pickup logging
- dashboard summaries
- basic AI chat over structured data

## Future scope
- semantic retrieval over notes
- thread-based AI assistant
- vision events from camera
- posture tracking