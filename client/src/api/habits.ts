import { apiFetch } from "./client";
import type { Habit, HabitCreate, HabitUpdate } from "./types";

export const habitsApi = {
  list: () => apiFetch<Habit[]>("/v1/habits/"),

  get: (id: string) => apiFetch<Habit>(`/v1/habits/${id}`),

  create: (data: HabitCreate) =>
    apiFetch<Habit>("/v1/habits/", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: HabitUpdate) =>
    apiFetch<Habit>(`/v1/habits/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  delete: (id: string) =>
    apiFetch<void>(`/v1/habits/${id}`, { method: "DELETE" }),
};
