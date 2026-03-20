# Phase 02 — Rev 02: Alembic Migrations & SQLAlchemy Models

## Context

**Branch:** `phase-02-core-db-table-implementation-rev-02`  
**Builds on:** Rev 01 (local Postgres container running via `make local-db-up`)  
**Goal:** Wire Alembic into the FastAPI backend so schema changes are version-controlled and repeatable. Define SQLAlchemy ORM models for all six core tables and apply the first migration.

---

## What was done

### 1. Added dependencies to `backend/pyproject.toml`

Four new packages added under `[tool.poetry.dependencies]`:

| Package | Version | Purpose |
|---|---|---|
| `sqlalchemy` | `^2.0` | ORM and Core SQL toolkit |
| `alembic` | `^1.13` | Database migration framework |
| `psycopg2-binary` | `^2.9` | PostgreSQL adapter for Python |
| `python-dotenv` | `^1.0` | Load `.env` files into `os.environ` |

```bash
cd backend && poetry lock && poetry install
```

`poetry lock` was required because the lock file had drifted from `pyproject.toml`.

---

### 2. Initialized Alembic

```bash
cd backend && poetry run alembic init migrations
```

This generated:

```
backend/
  alembic.ini                  ← Alembic config (points to migrations/)
  migrations/
    env.py                     ← Runtime environment for migrations
    script.py.mako             ← Template for new migration files
    README                     ← Alembic boilerplate
    versions/                  ← Migration files live here
```

---

### 3. Configured `alembic.ini`

The `sqlalchemy.url` line was cleared — the URL is injected at runtime from the environment:

```ini
# URL is set programmatically in migrations/env.py from the DATABASE_URL environment variable
sqlalchemy.url =
```

---

### 4. Configured `migrations/env.py`

Key changes from the generated default:

**a) Load `DATABASE_URL` from `infra/local/.env` automatically:**

```python
from pathlib import Path
from dotenv import load_dotenv

_dotenv_path = Path(__file__).resolve().parents[2] / "infra" / "local" / ".env"
load_dotenv(dotenv_path=_dotenv_path, override=False)
```

`parents[2]` resolves from `backend/migrations/env.py` → up two levels → workspace root → `infra/local/.env`.  
`override=False` means an already-set shell env var takes precedence over the file.

**b) Inject the URL into Alembic config:**

```python
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```

**c) Import models for autogenerate support:**

```python
from db.models import Base
target_metadata = Base.metadata
```

With `target_metadata` set, `alembic revision --autogenerate` can detect schema drift between models and the DB.

---

### 5. Added `DATABASE_URL` to `infra/local/.env.example`

```env
DATABASE_URL=postgresql://app_user:app_password@localhost:5432/habit_tracker
```

Developers need to add this line to their local `infra/local/.env` after copying the example.

---

### 6. Created `backend/db/models.py` — SQLAlchemy ORM models

Six tables defined using the modern SQLAlchemy 2.0 `Mapped` / `mapped_column` API with full type annotations:

#### `users`
```
id          UUID  PK  default gen_random_uuid()
created_at  timestamptz  server_default now()
updated_at  timestamptz  server_default now()
```

#### `habits`
```
id           UUID  PK
user_id      UUID  FK→users.id  CASCADE
name         varchar(255)
description  text  nullable
frequency    varchar(50)  default "daily"
is_active    boolean  default true
created_at   timestamptz
updated_at   timestamptz
```

#### `habit_logs`
```
id           UUID  PK
habit_id     UUID  FK→habits.id  CASCADE
user_id      UUID  FK→users.id   CASCADE
logged_date  date
notes        text  nullable
created_at   timestamptz
```
Indexes on `habit_id`, `user_id`, `logged_date`.

#### `bottle_events`
```
id         UUID  PK
user_id    UUID  FK→users.id  CASCADE
event_ts   timestamptz
volume_ml  integer
notes      text  nullable
created_at timestamptz
```
Indexes on `user_id`, `event_ts`.

#### `notes`
```
id         UUID  PK
user_id    UUID  FK→users.id  CASCADE
content    text
source     varchar(50)  default "manual"  (manual | ai)
created_at timestamptz
updated_at timestamptz
```

#### `daily_summaries`
```
id            UUID  PK
user_id       UUID  FK→users.id  CASCADE
summary_date  date
content       text
created_at    timestamptz
updated_at    timestamptz
```
Composite index on `(user_id, summary_date)` for efficient per-user date lookups.

All foreign keys use `ondelete="CASCADE"` so deleting a user removes all their data.

---

### 7. Created `backend/migrations/versions/0001_initial.py`

Handwritten migration (no autogenerate, so no live DB required during authoring). Implements `upgrade()` and `downgrade()`:

- `upgrade()`: creates all 6 tables with indexes in dependency order (users → habits → habit_logs, etc.)
- `downgrade()`: drops tables in reverse dependency order

Uses `gen_random_uuid()` (built into Postgres 13+) as PK default on all tables.

---

### 8. Added Makefile targets

Four new targets added to the root `Makefile`:

| Target | Command | When to use |
|---|---|---|
| `make db-migrate` | `alembic upgrade head` | Apply all pending migrations |
| `make db-downgrade` | `alembic downgrade -1` | Roll back the last migration |
| `make db-revision msg="..."` | `alembic revision --autogenerate -m "..."` | Create a new migration from model changes |
| `make db-history` | `alembic history --verbose` | Inspect the migration changelog |

---

## How to reproduce from scratch

### Prerequisites
- Docker Desktop running  
- `infra/local/.env` exists (copied from `.env.example` in Rev 01)

### Steps

```bash
# 1. Add DATABASE_URL to your local env file (once, after Rev 01 setup)
echo "DATABASE_URL=postgresql://app_user:app_password@localhost:5432/habit_tracker" >> infra/local/.env

# 2. Start Postgres (if not already running)
make local-db-up

# 3. Install backend dependencies
make backend-install

# 4. Run all migrations
make db-migrate
# Expected:
# INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, create initial tables

# 5. Verify tables were created
docker compose --env-file infra/local/.env -f infra/local/docker-compose.yml \
  exec postgres psql -U app_user -d habit_tracker -c "\dt"
# Expected: 7 rows — alembic_version + 6 app tables
```

### Creating a future migration

After changing `backend/db/models.py`:

```bash
make db-revision msg="add email column to users"
# Then review the generated file in backend/migrations/versions/
make db-migrate
```

---

## Files changed

| File | Change type |
|---|---|
| `backend/pyproject.toml` | Updated (added 4 dependencies) |
| `backend/poetry.lock` | Updated (regenerated) |
| `backend/alembic.ini` | Created by `alembic init`, configured |
| `backend/migrations/env.py` | Created by `alembic init`, extended with dotenv + models |
| `backend/migrations/script.py.mako` | Created by `alembic init` (unchanged) |
| `backend/migrations/README` | Created by `alembic init` (unchanged) |
| `backend/migrations/versions/0001_initial.py` | Created (handwritten migration) |
| `backend/db/__init__.py` | Created |
| `backend/db/models.py` | Created (6 SQLAlchemy models) |
| `infra/local/.env.example` | Updated (added `DATABASE_URL`) |
| `Makefile` | Updated (added 4 db-* targets) |
