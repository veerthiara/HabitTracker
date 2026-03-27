# Phase 03 Rev 03 — Full Feature Pages (Habits, Hydration, Notes)

## Goal

Replace all stub pages with fully working feature UIs. Users can now create habits, track streaks, log water intake, and write timestamped notes — all wired to the live backend API.

## Key Decisions

- **No sub-routing for habits** — habit detail stayed out of scope; everything renders on the list page via the HabitCard component.
- **Hydration uses inline form, not a modal** — water logging is high-frequency; removing the modal click reduces friction. Quick-select buttons (150/250/350/500 ml) further speed up the flow.
- **Notes compose area sits above the list** — mental model mirrors messaging apps; write at top, history below. `⌘↵` shortcut also supported.
- **Shared UI components (Modal, FormField) built once** — used by CreateHabitModal; Hydration/Notes chose simpler inline forms and raw inputs to match each page's interaction pattern.
- **`loading` prop (not `isLoading`)** — the custom Button component uses `loading`; caught and fixed during build verification.

## Architectural Context

This revision closes out Phase 03 (Manual Logging MVP). All four routes (`/`, `/habits`, `/hydration`, `/notes`) are now fully interactive. The frontend talks to the FastAPI backend exclusively via the typed ``apiFetch<T>()`` wrapper; React Query handles caching and invalidation across pages (for example, dashboard summary refreshes after a habit is marked done or a note is saved).

## Flow

```
User visits /habits
  → useQuery ["habits"] → habitsApi.list()
  → renders HabitCard grid
    → each card: 7-day dot grid, streak badge, Mark done / Undo
    → Mark done → useMutation → habitLogsApi.create() → invalidate ["habits"], ["dashboard"]
  → "+ New Habit" button → CreateHabitModal
    → form submit → habitsApi.create() → invalidate ["habits"], ["dashboard"] → modal closes

User visits /hydration
  → useQuery ["bottle-events", today] → bottleEventsApi.list(today)
  → progress bar fills based on totalMl / 2000ml goal
  → quick-select or custom volume input
  → "+ Log" → bottleEventsApi.create() → invalidate events + dashboard
  → event list (newest first) with per-row delete

User visits /notes
  → useQuery ["notes"] → notesApi.list()
  → textarea + "Save Note" (or ⌘↵) → notesApi.create() → invalidate notes + dashboard
  → list with left-accent border, relative timestamps, delete per note
```

## Scope Implemented

- `pages/Habits/HabitsPage.tsx` + `HabitsPage.module.css` — replaced stub; grid of HabitCards + CreateHabitModal
- `pages/Habits/components/CreateHabitModal.tsx` — form (name/description/frequency) with useMutation
- `pages/Habits/components/HabitCard.tsx` + `HabitCard.module.css` — 7-day grid, streak, mark done/undo
- `pages/Hydration/HydrationPage.tsx` + `HydrationPage.module.css` — progress bar, quick-pick form, event list
- `pages/Notes/NotesPage.tsx` + `NotesPage.module.css` — compose area, timestamped note list
- `components/ui/Modal.tsx` + `Modal.module.css` — reusable overlay (Escape + backdrop close)
- `components/ui/FormField.tsx` + `FormField.module.css` — InputField, TextareaField, SelectField

## Files Changed

```
client/src/
  components/ui/Modal.tsx
  components/ui/Modal.module.css
  components/ui/FormField.tsx
  components/ui/FormField.module.css
  pages/Habits/HabitsPage.tsx          ← replaced stub
  pages/Habits/HabitsPage.module.css   ← new
  pages/Habits/components/CreateHabitModal.tsx
  pages/Habits/components/HabitCard.tsx
  pages/Habits/components/HabitCard.module.css
  pages/Hydration/HydrationPage.tsx    ← replaced stub
  pages/Hydration/HydrationPage.module.css ← new
  pages/Notes/NotesPage.tsx            ← replaced stub
  pages/Notes/NotesPage.module.css     ← new
```

## Notes

- Build confirmed clean: `tsc -b && vite build` — 135 modules, 0 errors.
- Daily hydration goal is hardcoded at 2000 ml; could be a user setting in a later phase.
- Streak calculation in HabitCard is client-side from the 7-day log window; backend `daily_summary` table can serve this in Phase 04 if needed.

## Next Step

Phase 04 — pgvector semantic search foundation (embedding notes, semantic habit lookup).
