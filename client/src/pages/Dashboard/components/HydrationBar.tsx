import { Card, CardHeader } from "../../../components/ui/Card";
import styles from "./HydrationBar.module.css";

interface Props {
  totalMl: number;
  goalMl?: number;
}

export function HydrationBar({ totalMl, goalMl = 2500 }: Props) {
  const pct = Math.min(100, Math.round((totalMl / goalMl) * 100));

  const color =
    pct >= 100 ? "var(--color-success)" :
    pct >= 60  ? "var(--color-accent)"  :
                 "var(--color-warning)";

  return (
    <Card>
      <CardHeader
        title="Hydration Goal"
        subtitle={`${(totalMl / 1000).toFixed(1)} L of ${(goalMl / 1000).toFixed(1)} L`}
      />
      <div className={styles.track}>
        <div
          className={styles.fill}
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <p className={styles.label}>{pct}% of daily goal</p>
    </Card>
  );
}
