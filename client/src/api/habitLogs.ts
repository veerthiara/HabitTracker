import { apiFetch } from "./client";

export interface HabitLog {
  id: string;
  habit_id: string;
  user_id: string;
  logged_date: string;
  notes: string | null;
  created_at: string;
}

export const habitLogsApi = {
  list: (params?: { habit_id?: string; logged_date?: string }) => {
    const qs = new URLSearchParams();
    if (params?.habit_id) qs.set("habit_id", params.habit_id);
    if (params?.logged_date) qs.set("logged_date", params.logged_date);
    return apiFetch<HabitLog[]>(`/v1/habit-logs/${qs.toString() ? "?" + qs : ""}`);
  },

  create: (data: { habit_id: string; logged_date: string; notes?: string }) =>
    apiFetch<HabitLog>("/v1/habit-logs/", { method: "POST", body: JSON.stringify(data) }),

  delete: (id: string) =>
    apiFetch<void>(`/v1/habit-logs/${id}`, { method: "DELETE" }),
};
