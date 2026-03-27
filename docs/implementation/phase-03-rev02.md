# Phase 03 — Rev 02: Frontend Shell + Dashboard

## Goal

Build the application shell (sidebar navigation, layout) and a fully functional dashboard page that pulls live data from the backend API. Establish the design system, component structure, and API client layer used by all subsequent pages.

## Scope implemented

- Design tokens (CSS custom properties) — colors, spacing, typography, radii, shadows
- CSS reset
- Reusable UI primitives: `Button`, `Card`, `Badge`, `StatCard`, `Spinner`, `EmptyState`
- App shell: `AppShell` (layout wrapper), `Sidebar` (dark, icon + label nav), `TopBar` (page header)
- API client layer (`src/api/`) — typed fetch wrapper + one file per domain
- Dashboard page with four sub-components: `SummaryCards`, `HabitsToday`, `HydrationBar`, `RecentNotes`
- Inline "mark done" on `HabitsToday` with pop animation, optimistic invalidation via react-query
- Stub placeholder pages for Habits, Hydration, Notes (Rev 03)
- `react-router-dom` v7 + `@tanstack/react-query` v5 wired into providers

## Files changed

| File | Change |
|---|---|
| `client/package.json` | added react-router-dom, @tanstack/react-query |
| `client/src/main.tsx` | rewritten — QueryClientProvider + BrowserRouter |
| `client/src/App.tsx` | rewritten — route tree using AppShell as layout |
| `client/src/styles/tokens.css` | new — all design tokens |
| `client/src/styles/reset.css` | new — CSS reset |
| `client/src/components/ui/Button.tsx + .module.css` | new |
| `client/src/components/ui/Card.tsx + .module.css` | new |
| `client/src/components/ui/Badge.tsx + .module.css` | new |
| `client/src/components/ui/StatCard.tsx + .module.css` | new |
| `client/src/components/ui/Spinner.tsx + .module.css` | new |
| `client/src/components/ui/EmptyState.tsx + .module.css` | new |
| `client/src/components/layout/AppShell.tsx + .module.css` | new |
| `client/src/components/layout/Sidebar.tsx + .module.css` | new |
| `client/src/components/layout/TopBar.tsx + .module.css` | new |
| `client/src/api/client.ts` | new — base fetch wrapper with ApiError |
| `client/src/api/types.ts` | new — shared TypeScript types |
| `client/src/api/habits.ts` | new |
| `client/src/api/habitLogs.ts` | new |
| `client/src/api/bottleEvents.ts` | new |
| `client/src/api/notes.ts` | new |
| `client/src/api/dashboard.ts` | new |
| `client/src/pages/Dashboard/DashboardPage.tsx + .module.css` | new |
| `client/src/pages/Dashboard/components/SummaryCards.tsx + .module.css` | new |
| `client/src/pages/Dashboard/components/HabitsToday.tsx + .module.css` | new |
| `client/src/pages/Dashboard/components/HydrationBar.tsx + .module.css` | new |
| `client/src/pages/Dashboard/components/RecentNotes.tsx + .module.css` | new |
| `client/src/pages/Habits/HabitsPage.tsx` | new — stub |
| `client/src/pages/Hydration/HydrationPage.tsx` | new — stub |
| `client/src/pages/Notes/NotesPage.tsx` | new — stub |

## Design decisions

- No UI library — hand-crafted CSS Modules with token-driven design
- Dark sidebar (`#0d0f14`), light content area (`#f7f7f8`) — mirrors the Cycode-style layout requested
- Indigo (`#6366f1`) as the single accent color
- CSS Modules per component — zero global class conflicts, co-located styles
- Each Dashboard section is its own component with its own CSS module — easy to move to other pages

## Notes

- `HabitsToday` marks habits done inline and invalidates the `["dashboard"]` query — no page reload needed
- `HydrationBar` animates the fill via CSS transition on `width`
- The `api/client.ts` wrapper throws `ApiError` with HTTP status — components can distinguish 404 vs 500

## Next step

Phase 03 Rev 03 — implement full Habits, Hydration, and Notes feature pages.
