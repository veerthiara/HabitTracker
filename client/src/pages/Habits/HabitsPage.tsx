import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TopBar } from "../../components/layout/TopBar";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { habitsApi } from "../../api/habits";
import { HabitCard } from "./components/HabitCard";
import { CreateHabitModal } from "./components/CreateHabitModal";
import styles from "./HabitsPage.module.css";

function todayISO() {
  return new Date().toISOString().split("T")[0];
}

export function HabitsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const today = todayISO();

  const { data: habits, isLoading, isError } = useQuery({
    queryKey: ["habits"],
    queryFn: habitsApi.list,
    staleTime: 30_000,
  });

  return (
    <>
      <TopBar
        title="Habits"
        subtitle="Track your daily habits and streaks"
        action={
          <Button onClick={() => setShowCreate(true)} icon="＋">
            New Habit
          </Button>
        }
      />
      <div className={styles.content}>
        {isLoading && <Spinner center />}
        {isError && <p className={styles.error}>Failed to load habits.</p>}
        {habits && habits.length === 0 && (
          <EmptyState
            icon="✓"
            title="No habits yet"
            message="Create your first habit and start building your streak."
            action={<Button onClick={() => setShowCreate(true)}>Create Habit</Button>}
          />
        )}
        {habits && habits.length > 0 && (
          <div className={styles.grid}>
            {habits.map((habit) => (
              <HabitCard key={habit.id} habit={habit} today={today} />
            ))}
          </div>
        )}
      </div>

      <CreateHabitModal open={showCreate} onClose={() => setShowCreate(false)} />
    </>
  );
}
