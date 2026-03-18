# Client

Minimal React + Vite + TypeScript frontend.

## Prerequisites

- Node.js 20+
- npm

## Environment

Copy `.env.example` to `.env` and adjust if needed.

- `VITE_API_BASE_URL`: base URL used in browser requests. Default in code is `/api`.
- `VITE_BACKEND_ORIGIN`: Vite dev proxy target used for `/api/*` in local dev.

## Run locally

From the repo root:

```bash
make client-install
make client-run
```

This starts Vite on `http://127.0.0.1:5173` by default.

## Manual verification

1. Start backend (`make backend-run`) in one terminal.
2. Start frontend (`make client-run`) in another terminal.
3. Open `http://127.0.0.1:5173`.
4. Click **Call backend /**.
5. Verify status becomes `success` and response shows `Hello World`.

Backend curl check:

```bash
curl http://127.0.0.1:8000/
```

Expected response:

```json
{"message":"Hello World"}
```
