# Phase 02 — Rev 03: Seed Script

## Goal

Provide a reproducible, idempotent seed script that populates the local database with demo data so developers can start working immediately after running migrations.

## Scope implemented

- `backend/scripts/seed/` package — one module per domain
- Fixed UUIDs on every row + `INSERT … ON CONFLICT DO NOTHING` → safe to run many times
- Single orchestrator (`main.py`) that loads `DATABASE_URL`, opens one session, calls all seeders, commits once
- `make db-seed` Makefile target

## Files changed

| File | Change |
|---|---|
| `backend/scripts/__init__.py` | new — package marker |
| `backend/scripts/seed/__init__.py` | new — package marker |
| `backend/scripts/seed/users.py` | new — 1 demo user (`…0001`) |
| `backend/scripts/seed/habits.py` | new — 3 habits + 14 habit logs (2 habits × 7 days) |
| `backend/scripts/seed/bottle_events.py` | new — 3 hydration events for today |
| `backend/scripts/seed/notes.py` | new — 2 manual notes |
| `backend/scripts/seed/main.py` | new — orchestrator; loads `.env`, runs all seeders |
| `Makefile` | added `db-seed` target |
| `backend/README.md` | added seed usage section + table of demo data |

## How to run

```bash
# DB must be running and migrated first
make local-db-up
make db-migrate

# Seed (safe to run multiple times)
make db-seed
```

## Notes

- Seed data is **local dev only** — never runs via Alembic, never touches staging/prod
- All IDs are in the `00000000-0000-0000-0000-0000000XXXXX` range — easy to spot and filter out
- Adding new seed data: create a new module under `scripts/seed/`, add a `seed(session)` function, register it in `main.py`

## Next step

Phase 03 — manual MVP API endpoints (CRUD for habits and habit logs via FastAPI).
