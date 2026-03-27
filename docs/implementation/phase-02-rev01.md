# Phase 02 — Rev 01: Local PostgreSQL Infrastructure

## Context

**Branch:** `phase-02-core-db-table-implementation-rev-01`  
**Goal:** Spin up a local PostgreSQL container that the backend can connect to for development and migration work.

---

## What was done

### 1. Created `infra/local/docker-compose.yml`

Added a dedicated Docker Compose file for local infrastructure, separate from the application's main `docker-compose.yml`. This keeps dev infrastructure isolated and independently startable.

```yaml
services:
  postgres:
    image: postgres:16
    container_name: habit-local-postgres
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app_user} -d ${POSTGRES_DB:-habit_tracker}"]
      interval: 5s
      timeout: 3s
      retries: 20

volumes:
  pg_data:
```

Key decisions:
- Uses `postgres:16` (stable, LTS)
- All credentials sourced from `.env` — never hardcoded
- Named volume `pg_data` persists data across container restarts
- Healthcheck ensures the container is truly ready before dependent services start

---

### 2. Created `infra/local/.env.example`

Template for the local environment file. Developers copy this to `.env` and adjust values as needed.

```env
POSTGRES_USER=app_user
POSTGRES_PASSWORD=app_password
POSTGRES_DB=habit_tracker
POSTGRES_PORT=5432
```

The actual `infra/local/.env` is gitignored.

---

### 3. Updated `.gitignore`

Added `infra/local/.env` to prevent accidental commits of local credentials.

```
infra/local/.env
```

---

### 4. Added Makefile targets

Five new targets were added to the root `Makefile` to manage the local database container without needing to remember Docker Compose flags:

| Target | What it does |
|---|---|
| `make local-db-up` | Start the Postgres container in the background |
| `make local-db-down` | Stop and remove the container |
| `make local-db-logs` | Tail the Postgres container logs |
| `make local-db-ps` | Show container status |
| `make local-db-check` | Run `SELECT 1` inside the container to verify connectivity |

All targets pass `--env-file infra/local/.env` and `-f infra/local/docker-compose.yml` to scope to the local infra compose file.

---

### 5. Updated `backend/README.md`

Added a "Local database" section pointing developers to copy the env example and run `make local-db-up` before doing migration work.

---

### 6. Created `infra/local/README.md`

Full step-by-step documentation for the local DB infra, including setup, verification, and teardown commands with expected outputs.

---

## How to reproduce from scratch

```bash
# 1. Copy the env template
cp infra/local/.env.example infra/local/.env

# 2. Start Postgres
make local-db-up

# 3. Verify container is healthy
make local-db-ps

# 4. Run a connectivity check
make local-db-check
# Expected: a row with "1" under the ?column? header

# 5. Tail logs if needed
make local-db-logs

# 6. Stop when done
make local-db-down
```

---

## Files changed

| File | Change type |
|---|---|
| `infra/local/docker-compose.yml` | Created |
| `infra/local/.env.example` | Created |
| `infra/local/README.md` | Created |
| `.gitignore` | Updated (added `infra/local/.env`) |
| `Makefile` | Updated (added 5 local-db-* targets) |
| `backend/README.md` | Updated (added local database section) |
