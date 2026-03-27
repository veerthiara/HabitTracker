import { apiFetch } from "./client";
import type { Habit } from "./types";
import type { Note } from "./notes";

export interface HabitSummary {
  habit: Habit;
  done_today: boolean;
}

export interface DashboardSummary {
  habits_total: number;
  habits_done_today: number;
  hydration_today_ml: number;
  habit_summaries: HabitSummary[];
  recent_notes: Note[];
}

export const dashboardApi = {
  summary: (date?: string) => {
    const qs = date ? `?date=${date}` : "";
    return apiFetch<DashboardSummary>(`/v1/dashboard/summary${qs}`);
  },
};
