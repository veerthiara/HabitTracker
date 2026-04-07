# Langfuse — Local LLM Observability

This folder runs a self-hosted [Langfuse](https://langfuse.com/) instance for local LLM observability and debugging, similar to LangSmith but fully local and open source.

## What is Langfuse?

Langfuse is an open-source LLM engineering platform that provides:

- **Tracing** — inspect every LLM call, chain, and agent step
- **Prompt management** — version and evaluate prompts
- **Scoring & evaluation** — attach quality scores to traces
- **Cost tracking** — monitor token usage and cost per request
- **Dashboard** — visual overview of latency, errors, and usage

## Architecture

```
┌──────────────────────────────────┐
│  HabitTracker Backend (FastAPI)  │
│  · LangGraph / Ollama calls      │
│  · langfuse SDK sends traces     │
└────────────┬─────────────────────┘
             │  HTTP (traces)
             ▼
┌──────────────────────────────────┐
│  Langfuse Server (:3100)         │
│  · Web UI + API                  │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│  Langfuse Postgres (:5433)       │
│  · Trace storage                 │
│  · Separate from app DB          │
└──────────────────────────────────┘
```

## Quick Start

1. Copy the env file:

```bash
cp infra/local/langfuse/.env.example infra/local/langfuse/.env
```

2. Start Langfuse:

```bash
make langfuse-up
```

3. Open the dashboard:

```
http://localhost:3100
```

4. Login with the default credentials:

| Field    | Value              |
| -------- | ------------------ |
| Email    | `admin@local.dev`  |
| Password | `admin123`         |

## Default API Keys

The compose file auto-creates a project with these keys (no manual setup needed):

| Key            | Value               |
| -------------- | ------------------- |
| Public Key     | `lf-pk-local-dev`   |
| Secret Key     | `lf-sk-local-dev`   |

Use these in your backend `.env` to connect the app to Langfuse (see "Backend Integration" below).

## Make Targets

| Command            | Description                              |
| ------------------ | ---------------------------------------- |
| `make langfuse-up`    | Start Langfuse (server + postgres)       |
| `make langfuse-down`  | Stop Langfuse                            |
| `make langfuse-logs`  | Follow Langfuse container logs           |
| `make langfuse-ps`    | Show Langfuse container status           |
| `make langfuse-reset` | Destroy volumes and restart (data loss)  |

## Backend Integration

To send traces from the HabitTracker backend to Langfuse, add these to your backend environment:

```bash
LANGFUSE_PUBLIC_KEY=lf-pk-local-dev
LANGFUSE_SECRET_KEY=lf-sk-local-dev
LANGFUSE_HOST=http://localhost:3100
```

Then install the SDK in the backend:

```bash
cd backend && poetry add langfuse
```

## Ports

| Service           | Port  | Notes                                  |
| ----------------- | ----- | -------------------------------------- |
| Langfuse Web UI   | 3100  | Dashboard & API                        |
| Langfuse Postgres | 5433  | Separate from app DB (port 5432)       |

## Troubleshooting

- **Port conflict on 3100**: Change `ports` mapping in `docker-compose.yml` and update `NEXTAUTH_URL` in `.env`
- **Port conflict on 5433**: Change `LANGFUSE_POSTGRES_PORT` in `.env`
- **Container won't start**: Run `make langfuse-logs` to inspect errors
- **Fresh start needed**: Run `make langfuse-reset` (destroys all trace data)
