# Phase 03 — Rev 01: Backend API (FastAPI CRUD)

## Goal

Build the full REST API for the Manual Logging MVP: habits, habit logs, bottle events, notes, and a dashboard summary endpoint. Structure the backend so every concern (schema, persistence, routing, app wiring) lives in its own layer.

## Scope implemented

- Upgraded FastAPI to 0.115 and Pydantic to v2
- Pydantic v2 schemas with validation for all five domains
- Repository layer — plain functions, no base class, session passed as argument
- FastAPI routers under `/api/v1/` with correct HTTP status codes
- Health endpoints moved to `habittracker/api/health.py` (no version prefix)
- Application factory `habittracker/server.py` (`create_application() → FastAPI`)
- `main.py` reduced to two lines: import factory + `uvicorn.run`
- CORS configured for the local Vite dev server

## Files changed

| File | Change |
|---|---|
| `backend/pyproject.toml` | fastapi → 0.115, uvicorn[standard] → 0.29, pydantic → 2.x |
| `backend/main.py` | rewritten — uvicorn entry point only |
| `backend/habittracker/server.py` | new — `create_application()` factory |
| `backend/habittracker/api/__init__.py` | new — package marker |
| `backend/habittracker/api/deps.py` | new — `get_current_user_id()` (demo placeholder) |
| `backend/habittracker/api/health.py` | new — `/health`, `/ready` |
| `backend/habittracker/api/v1/__init__.py` | new — package marker |
| `backend/habittracker/api/v1/habits.py` | new — full CRUD (soft-delete) |
| `backend/habittracker/api/v1/habit_logs.py` | new — create / list / delete + 409 on duplicate |
| `backend/habittracker/api/v1/bottle_events.py` | new — create / list by date / delete |
| `backend/habittracker/api/v1/notes.py` | new — create / list / delete |
| `backend/habittracker/api/v1/dashboard.py` | new — `GET /api/v1/dashboard/summary?date=` |
| `backend/habittracker/schemas/__init__.py` | new — package marker |
| `backend/habittracker/schemas/habit.py` | new |
| `backend/habittracker/schemas/habit_log.py` | new |
| `backend/habittracker/schemas/bottle_event.py` | new |
| `backend/habittracker/schemas/note.py` | new |
| `backend/habittracker/schemas/dashboard.py` | new |
| `backend/habittracker/models/repository/__init__.py` | new — package marker |
| `backend/habittracker/models/repository/session.py` | new — `get_session()` dependency |
| `backend/habittracker/models/repository/habit_repository.py` | new |
| `backend/habittracker/models/repository/habit_log_repository.py` | new |
| `backend/habittracker/models/repository/bottle_event_repository.py` | new |
| `backend/habittracker/models/repository/note_repository.py` | new |
| `backend/habittracker/models/repository/dashboard_repository.py` | new |

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | |
| GET | `/ready` | |
| GET | `/api/v1/habits/` | Active habits for current user |
| POST | `/api/v1/habits/` | 201 Created |
| GET | `/api/v1/habits/{id}` | 404 if not found |
| PATCH | `/api/v1/habits/{id}` | Partial update |
| DELETE | `/api/v1/habits/{id}` | Soft-delete (sets `is_active=False`) |
| GET | `/api/v1/habit-logs/?habit_id=&logged_date=` | Filter by either or both |
| POST | `/api/v1/habit-logs/` | 409 if already logged for that date |
| DELETE | `/api/v1/habit-logs/{id}` | |
| GET | `/api/v1/bottle-events/?date=` | Filter by UTC calendar day |
| POST | `/api/v1/bottle-events/` | |
| DELETE | `/api/v1/bottle-events/{id}` | |
| GET | `/api/v1/notes/` | Newest first, limit 50 |
| POST | `/api/v1/notes/` | |
| DELETE | `/api/v1/notes/{id}` | |
| GET | `/api/v1/dashboard/summary?date=` | Defaults to today |

## Notes

- Auth is not implemented. `get_current_user_id()` in `api/deps.py` returns the hardcoded demo UUID. Replace with JWT extraction in a future phase.
- Habit delete is a soft-delete to preserve historical log data.
- Session is created per request via `get_session()` using `pool_pre_ping=True`.

## Next step

Phase 03 Rev 02 — Frontend shell + Dashboard page using React, react-router-dom, and @tanstack/react-query.
