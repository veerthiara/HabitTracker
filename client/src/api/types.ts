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
