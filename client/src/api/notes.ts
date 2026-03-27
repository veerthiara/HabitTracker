import { apiFetch } from "./client";

export interface Note {
  id: string;
  user_id: string;
  content: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export const notesApi = {
  list: () => apiFetch<Note[]>("/v1/notes/"),

  create: (data: { content: string; source?: string }) =>
    apiFetch<Note>("/v1/notes/", { method: "POST", body: JSON.stringify(data) }),

  delete: (id: string) =>
    apiFetch<void>(`/v1/notes/${id}`, { method: "DELETE" }),
};
