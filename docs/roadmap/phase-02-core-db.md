# Phase 02 — Core Database

## Goal
Set up Postgres and create the core transactional schema.

## Scope
- add Postgres to docker-compose
- add migrations
- create initial tables:
  - users
  - habits
  - habit_logs
  - bottle_events
  - notes
  - daily_summaries

## Deliverable
- database starts locally
- migrations run successfully
- seed script can insert basic demo data

## Out of scope
- pgvector
- embeddings
- AI chat