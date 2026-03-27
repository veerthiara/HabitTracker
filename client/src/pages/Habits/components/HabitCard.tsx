import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Spinner } from "../../../components/ui/Spinner";
import { EmptyState } from "../../../components/ui/EmptyState";
import { habitLogsApi } from "../../../api/habitLogs";
import type { Habit } from "../../../api/types";
import styles from "./HabitCard.module.css";

interface Props {
  habit: Habit;
  today: string;
}

function todayLabel(loggedDates: string[], today: string): { streak: number; doneToday: boolean } {
  const sorted = [...loggedDates].sort().reverse();
  const doneToday = sorted[0] === today;
  let streak = doneToday ? 1 : 0;
  for (let i = doneToday ? 1 : 0; i < sorted.length; i++) {
    const prev = new Date(sorted[i - 1 + (doneToday ? 0 : 0)]);
    const curr = new Date(sorted[i]);
    const diff = (prev.getTime() - curr.getTime()) / 86400000;
    if (diff === 1) streak++;
    else break;
  }
  return { streak, doneToday };
}

export function HabitCard({ habit, today }: Props) {
  const qc = useQueryClient();

  const { data: logs, isLoading } = useQuery({
    queryKey: ["habit-logs", habit.id],
    queryFn: () => habitLogsApi.list({ habit_id: habit.id }),
    staleTime: 30_000,
  });

  const logMutation = useMutation({
    mutationFn: () => habitLogsApi.create({ habit_id: habit.id, logged_date: today }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["habit-logs", habit.id] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => habitLogsApi.delete(
      logs!.find((l) => l.logged_date === today)!.id
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["habit-logs", habit.id] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const loggedDates = logs?.map((l) => l.logged_date) ?? [];
  const { streak, doneToday } = todayLabel(loggedDates, today);
  const last7 = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    const key = d.toISOString().split("T")[0];
    return { key, done: loggedDates.includes(key) };
  });

  return (
    <Card padding="md">
      <div className={styles.header}>
        <div className={styles.meta}>
          <p className={styles.name}>{habit.name}</p>
          {habit.description && <p className={styles.desc}>{habit.description}</p>}
        </div>
        <div className={styles.badges}>
          <Badge label={habit.frequency} color="default" />
          {streak > 1 && <Badge label={`🔥 ${streak} streak`} color="warning" />}
        </div>
      </div>

      {/* 7-day grid */}
      {isLoading ? (
        <Spinner size="sm" />
      ) : (
        <div className={styles.grid}>
          {last7.map(({ key, done }) => (
            <div key={key} className={[styles.dot, done ? styles.dotDone : ""].join(" ")} title={key} />
          ))}
        </div>
      )}

      <div className={styles.footer}>
        <span className={styles.streak}>{streak > 0 ? `${streak}-day streak` : "No streak yet"}</span>
        {doneToday ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => deleteMutation.mutate()}
            loading={deleteMutation.isPending}
          >
            Undo
          </Button>
        ) : (
          <Button
            size="sm"
            onClick={() => logMutation.mutate()}
            loading={logMutation.isPending}
          >
            Mark done
          </Button>
        )}
      </div>
    </Card>
  );
}
