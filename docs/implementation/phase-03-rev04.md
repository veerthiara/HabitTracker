# Phase 03 Rev 04 — Environment Variable Configuration

## Goal

Route frontend API calls to the correct backend URL per environment (local, dev, prod) using Vite's built-in environment file loading, without any code changes between environments.

## Key Decisions

- **Use Vite's mode-based env files** (`--mode development` / `--mode production`) rather than a custom approach. Vite loads `.env.[mode]` files automatically, so no runtime switching logic is needed in application code.
- **`VITE_API_BASE_URL` as a full URL for dev/prod** — the initial setup used `/api` (relative) which works via Vite's proxy but fails in any deployed environment where proxy is unavailable. Switching to an absolute URL makes the same code work in all environments.
- **`.env.production` is gitignored** — it will contain real deployment URLs. `.env.development` is committed because it only contains local loopback addresses (no secrets).
- **`client/.env` (machine-level override) stays gitignored** — developers can still override locally without touching the committed `.env.development`.

## Architectural Context

`client/src/api/client.ts` reads `import.meta.env.VITE_API_BASE_URL` at build time. Vite replaces this with the value from the active env file, so the built JS bundle already has the correct URL baked in — no runtime config file needed. The `VITE_BACKEND_ORIGIN` variable is only consumed by `vite.config.ts` for the dev-server proxy; it has no effect in production builds.

## Environment File Hierarchy

```
npm run dev           → mode=development → loads .env + .env.development
npm run build         → mode=production  → loads .env + .env.production
npm run build:dev     → mode=development → useful for building a dev-env deploy
```

Vite loads files in this priority order (higher overrides lower):
1. `.env.[mode].local`  (gitignored, highest priority)
2. `.env.[mode]`
3. `.env.local`         (gitignored)
4. `.env`

## Scope Implemented

- `client/.env.development` — local dev values, committed
- `client/.env.production` — prod placeholder, **gitignored**
- `client/.env.example` — updated template with full documentation
- `client/package.json` — explicit `--mode` flags on all scripts + new `build:dev` script
- `.gitignore` — added `client/.env.production` and `client/.env.*.local`

## Files Changed

```
client/.env.development        ← new, committed
client/.env.production         ← new, gitignored
client/.env.example            ← updated
client/package.json            ← scripts: explicit --mode flags + build:dev
.gitignore                     ← added env.production + env.*.local patterns
docs/implementation/phase-03-rev04.md ← this file
```

## Notes

- Build confirmed clean: `tsc -b && vite build --mode production` — 135 modules, 0 errors.
- When deploying, copy `.env.example` → `.env.production`, fill in real URLs, then `npm run build`.
- For a staging server, either rename it `.env.staging` and run `vite build --mode staging`, or just override `.env.production` on the CI/CD server.

## Next Step

Phase 04 — pgvector semantic search (embedding notes, semantic habit lookup).
