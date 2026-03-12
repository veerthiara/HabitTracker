# Backend

FastAPI backend for the `langchain-pgvector` monorepo.

## Prerequisites

- Python 3.11+
- Poetry

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