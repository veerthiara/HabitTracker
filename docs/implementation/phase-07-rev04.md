# Phase 07 Rev 04 — Integration + Polish

## Goal

Complete the Phase 07 chat integration by wiring an "Ask AI" entry point directly into the Dashboard page, and confirming layout integrity for the dual-panel chat experience.

## Key Decisions

- **"Ask AI" button via `TopBar`'s existing `action` prop** — `TopBar` already accepts a `React.ReactNode` action slot. No changes to the layout component were needed; a single `Button` passed down was sufficient.
- **`useChat().togglePanel` as the click handler** — reuses the same toggle already wired to the Sidebar button, keeping a single source of truth for panel open state.
- **No body-scroll fixes required** — `AppShell.module.css` already applies `overflow: hidden` on the shell and `overflow-y: auto` on the main content column. Both chat and evidence panels are `position: fixed` with their own `overflow-y: auto` bodies, so scroll areas are already fully independent.
- **Loading / error / auto-scroll already covered in Rev 02** — not re-implemented.

## Architectural Context

This completes the Phase 07 UI surface. The chat pipeline (Phase 06 LangGraph) is now reachable from the primary user landing page without navigating to a separate route or hunting for the sidebar toggle.

```
DashboardPage
  └─ TopBar action="◐ Ask AI"
        └─ useChat().togglePanel()
              └─ ChatPanel slides in (right: 0)
                    └─ EvidenceDrawer slides in (right: 420px) on message evidence click
```

## Scope Implemented

- "Ask AI" button in Dashboard TopBar — opens chat panel
- AppShell scroll layout verified (no changes needed)

## Files Changed

```
client/src/pages/Dashboard/DashboardPage.tsx
```

## Notes

- `Button variant="primary"` used for visual prominence on the Dashboard page; the Sidebar button uses a ghost/icon style. Both toggle the same panel.
- The EvidenceDrawer slide-in CSS bug (`translateX(100%)` not pushing far enough off-screen) was fixed in the same commit batch as Rev 03.

## Next Step

Phase 07 is complete. Next: Phase 08 — Vision Foundation (future/experimental).
