import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/Dashboard/DashboardPage";
import { HabitsPage } from "./pages/Habits/HabitsPage";
import { HydrationPage } from "./pages/Hydration/HydrationPage";
import { NotesPage } from "./pages/Notes/NotesPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="habits" element={<HabitsPage />} />
        <Route path="hydration" element={<HydrationPage />} />
        <Route path="notes" element={<NotesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
