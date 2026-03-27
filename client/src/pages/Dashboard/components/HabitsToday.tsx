import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge } from "../../../components/ui/Badge";
import { Card, CardHeader } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { habitLogsApi } from "../../../api/habitLogs";
import type { HabitSummary } from "../../../api/dashboard";
import styles from "./HabitsToday.module.css";

interface Props {
  summaries: HabitSummary[];
  today: string;
}

export function HabitsToday({ summaries, today }: Props) {
  const qc = useQueryClient();
  const logMutation = useMutation({
    mutationFn: (habitId: string) =>
      habitLogsApi.create({ habit_id: habitId, logged_date: today }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  return (
    <Card>
      <CardHeader title="Today's Habits" subtitle={today} />
      {summaries.length === 0 ? (
        <EmptyState icon="✓" title="No habits yet" message="Add your first habit to start tracking." />
      ) : (
        <ul className={styles.list}>
          {summaries.map(({ habit, done_today }) => (
            <li key={habit.id} className={styles.item}>
              <button
                className={[styles.check, done_today ? styles.checked : ""].join(" ")}
                onClick={() => !done_today && logMutation.mutate(habit.id)}
                disabled={done_today || logMutation.isPending}
                title={done_today ? "Done!" : "Mark as done"}
              >
                {done_today ? "✓" : ""}
              </button>
              <div className={styles.info}>
                <span className={[styles.name, done_today ? styles.done : ""].join(" ")}>
                  {habit.name}
                </span>
                {habit.description && (
                  <span className={styles.desc}>{habit.description}</span>
                )}
              </div>
              <Badge
                label={habit.frequency}
                color={done_today ? "success" : "default"}
              />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
