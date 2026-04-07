---
sidebar_position: 3
---

# Local Infrastructure

All local development infrastructure is managed via Docker Compose files under `infra/local/`. Each service has its own subdirectory with a dedicated `docker-compose.yml`, `.env.example`, and `README.md`.

## Overview

```
infra/local/
├── docker-compose.yml          # App Postgres (pgvector)
├── .env.example                # App DB env vars
├── README.md                   # App DB setup guide
└── langfuse/
    ├── docker-compose.yml      # Langfuse server + its own Postgres
    ├── .env.example            # Langfuse env vars
    └── README.md               # Langfuse setup guide
```

## Services

| Service              | Purpose                        | Port(s) | Compose File                            |
| -------------------- | ------------------------------ | ------- | --------------------------------------- |
| **Postgres (app)**   | Application database (pgvector)| 5432    | `infra/local/docker-compose.yml`        |
| **Langfuse Server**  | LLM observability dashboard    | 3100    | `infra/local/langfuse/docker-compose.yml` |
| **Langfuse Postgres**| Langfuse trace storage         | 5433    | `infra/local/langfuse/docker-compose.yml` |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- `make` available in your terminal

## Quick Start — Full Local Stack

```bash
# 1. Copy env files
cp infra/local/.env.example infra/local/.env
cp infra/local/langfuse/.env.example infra/local/langfuse/.env

# 2. Start app database
make local-db-up

# 3. Run migrations & seed
make db-migrate
make db-seed

# 4. Start Langfuse (optional — for LLM observability)
make langfuse-up

# 5. Start backend
make backend-run

# 6. Start frontend (separate terminal)
make client-run
```

## Service Details

### Application Postgres

The main application database uses the `pgvector/pgvector:pg16` image to support vector similarity search for semantic features.

| Make Target        | Description                                       |
| ------------------ | ------------------------------------------------- |
| `make local-db-up`    | Start app Postgres                                |
| `make local-db-down`  | Stop app Postgres                                 |
| `make local-db-reset` | Destroy volume and restart (data loss)            |
| `make local-db-logs`  | Follow Postgres logs                              |
| `make local-db-ps`    | Show container status                             |
| `make local-db-check` | Run a basic connectivity check                    |

See [infra/local/README.md](https://github.com/your-org/HabitTracker/blob/main/infra/local/README.md) for full details.

### Langfuse (LLM Observability)

Self-hosted [Langfuse](https://langfuse.com/) instance for tracing and debugging LLM calls from the LangGraph-powered chat backend. This is the local alternative to hosted services like LangSmith.

| Make Target          | Description                                     |
| -------------------- | ----------------------------------------------- |
| `make langfuse-up`      | Start Langfuse stack                            |
| `make langfuse-down`    | Stop Langfuse stack                             |
| `make langfuse-reset`   | Destroy volumes and restart (data loss)         |
| `make langfuse-logs`    | Follow all Langfuse container logs              |
| `make langfuse-ps`      | Show Langfuse container status                  |

**Dashboard**: http://localhost:3100  
**Default Login**: `admin@local.dev` / `admin123`

See [infra/local/langfuse/README.md](https://github.com/your-org/HabitTracker/blob/main/infra/local/langfuse/README.md) for full details including backend SDK integration steps.

## Port Map

| Port | Service              |
| ---- | -------------------- |
| 3100 | Langfuse Web UI      |
| 5432 | App Postgres         |
| 5433 | Langfuse Postgres    |
| 8000 | Backend (FastAPI)    |
| 5173 | Frontend (Vite dev)  |

## Adding New Local Services

To add a new local service:

1. Create a new folder under `infra/local/<service-name>/`
2. Add `docker-compose.yml`, `.env.example`, and `README.md`
3. Add corresponding `make` targets to the root `Makefile`
4. Update this document with the new service details
