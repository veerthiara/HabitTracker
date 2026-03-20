# Backend

FastAPI backend for the `langchain-pgvector` monorepo.

## Prerequisites

- Python 3.11+
- Poetry

## Local database

Start local PostgreSQL from the infrastructure folder before running migration-related backend work:

```bash
cp infra/local/.env.example infra/local/.env
make local-db-up
```

Infra documentation is available at `infra/local/README.md`.

## Local-only files

- `.venv/` is the Poetry virtual environment for this service.
- `.env` is reserved for backend-only environment variables.
- Service-local `.env` files and virtualenv directories are gitignored from the repo root.

## Run locally

From the repo root, install backend dependencies:

```bash
make backend-install
```

Start the API on `http://127.0.0.1:8000`:

```bash
make backend-run
```

Verify the health endpoint from a second terminal:

```bash
make backend-health
```

Expected response:

```json
{"status":"ok"}
```

Direct curl examples:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

## Docker Compose

From the repo root:

```bash
make backend-docker-up
```

Stop the container:

```bash
make backend-docker-down
```

## Project layout

```
backend/
  habittracker/               ← application package
    models/
      orm/
        base.py               ← DeclarativeBase (single source of truth)
        __init__.py           ← imports + re-exports all ORM models
        habittracker/         ← one file per domain model
          user.py
          habit.py
          habit_log.py
          bottle_event.py
          note.py
          daily_summary.py
  alembic/                    ← Alembic env + migration versions
    env.py
    versions/
  alembic.ini
  main.py
```

## Database migrations (Alembic)

Alembic is configured in `alembic.ini`. All commands are run from the
`backend/` directory (the Makefile `cd backend &&` prefix handles this).

### Apply all pending migrations

```bash
make db-migrate
```

### Roll back one migration

```bash
make db-downgrade
```

### Generate a new migration from model changes

```bash
make db-revision msg="describe what changed"
```

### View migration history

```bash
make db-history
```

### How autogenerate picks up models

`alembic/env.py` imports `Base` from `habittracker.models.orm`, which in
turn imports every model file so they register themselves with
`Base.metadata` before Alembic inspects it.