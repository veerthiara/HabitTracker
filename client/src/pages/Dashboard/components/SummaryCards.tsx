import { StatCard } from "../../../components/ui/StatCard";
import type { DashboardSummary } from "../../../api/dashboard";
import styles from "./SummaryCards.module.css";

interface Props {
  data: DashboardSummary;
}

export function SummaryCards({ data }: Props) {
  const completion = data.habits_total > 0
    ? Math.round((data.habits_done_today / data.habits_total) * 100)
    : 0;

  const hydrationL = (data.hydration_today_ml / 1000).toFixed(1);

  return (
    <div className={styles.grid}>
      <StatCard
        label="Habits done today"
        value={`${data.habits_done_today} / ${data.habits_total}`}
        sub={`${completion}% complete`}
        icon="✓"
        accent
      />
      <StatCard
        label="Hydration today"
        value={`${hydrationL} L`}
        sub={`${data.hydration_today_ml} ml logged`}
        icon="◉"
      />
      <StatCard
        label="Active habits"
        value={data.habits_total}
        sub="currently tracking"
        icon="◈"
      />
      <StatCard
        label="Notes"
        value={data.recent_notes.length}
        sub="recent entries"
        icon="◎"
      />
    </div>
  );
}
