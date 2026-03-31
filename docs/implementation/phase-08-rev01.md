# Phase 08 Rev 01 — Local Langfuse Stack

## Goal

Stand up a self-hosted Langfuse observability stack locally so developers can trace LLM calls before any backend code is touched.

## Key Decisions

- **Dedicated `infra/local/langfuse/` directory** — keeps Langfuse infra separate from the main app docker-compose, consistent with how the project separates infrastructure concerns.
- **Separate Postgres instance for Langfuse** — Langfuse requires its own database. Using a separate container avoids schema conflicts with the application Postgres.
- **`.env.example` with auto-init keys** — Langfuse requires SALT and encryption keys at boot. The example file ships with safe local-only placeholder values so `make langfuse-up` works out of the box without manual key generation.
- **`LANGFUSE_TRACING_ENABLED` flag** — gives developers a single toggle to disable tracing without removing env vars.

## Architectural Context

This is pure infrastructure: no backend code changes in this revision. The Langfuse server runs as a sidecar stack alongside the existing `infra/local/docker-compose.yml`.

```
make langfuse-up
  └─ infra/local/langfuse/docker-compose.yml
        ├─ langfuse-server   → localhost:3000
        └─ langfuse-postgres → internal only
```

## Scope Implemented

- `infra/local/langfuse/docker-compose.yml` — Langfuse server + dedicated Postgres
- `infra/local/langfuse/.env.example` — local credentials + keys
- `infra/local/langfuse/README.md` — setup guide + backend integration steps
- `docs/architecture/local-infrastructure.md` — infrastructure overview
- `Makefile` — `langfuse-up`, `langfuse-down`, `langfuse-logs`, `langfuse-ps`, `langfuse-reset`
- `docs/roadmap/phase-08-langfuse-tracking.md` — full phase plan

## Files Changed

```
Makefile
docs/architecture/local-infrastructure.md
docs/roadmap/phase-08-langfuse-tracking.md
infra/local/langfuse/.env.example
infra/local/langfuse/README.md
infra/local/langfuse/docker-compose.yml
```

## Notes

- `make langfuse-up` assumes `.env` is copied from `.env.example` in the same directory.
- Langfuse UI is at `http://localhost:3000` once running.

## Next Step

Rev 02 — wire `langfuse` Python SDK into the backend chat pipeline via a LangChain CallbackHandler.
