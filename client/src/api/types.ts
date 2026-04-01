export interface Habit {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  frequency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HabitCreate {
  name: string;
  description?: string;
  frequency?: string;
}

export interface HabitUpdate {
  name?: string;
  description?: string;
  frequency?: string;
  is_active?: boolean;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

/** A single piece of structured evidence returned with a chat answer. */
export interface EvidenceItem {
  type: string;   // e.g. "metric", "note", "habit"
  label: string;  // human-readable label
  value: string;  // the data value
}

/** Request body for POST /api/v1/chat/ */
export interface ChatRequest {
  message: string;
  thread_id?: string;
}

/** Response body from POST /api/v1/chat/ */
export interface ChatResponse {
  answer: string;
  intent: string;
  used_notes: boolean;
  evidence: EvidenceItem[];
  thread_id: string;
}
