import { apiFetch } from "./client";

export interface BottleEvent {
  id: string;
  user_id: string;
  event_ts: string;
  volume_ml: number;
  notes: string | null;
  created_at: string;
}

export const bottleEventsApi = {
  list: (date?: string) => {
    const qs = date ? `?date=${date}` : "";
    return apiFetch<BottleEvent[]>(`/v1/bottle-events/${qs}`);
  },

  create: (data: { event_ts: string; volume_ml: number; notes?: string }) =>
    apiFetch<BottleEvent>("/v1/bottle-events/", { method: "POST", body: JSON.stringify(data) }),

  delete: (id: string) =>
    apiFetch<void>(`/v1/bottle-events/${id}`, { method: "DELETE" }),
};
