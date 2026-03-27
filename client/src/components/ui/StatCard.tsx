import styles from "./StatCard.module.css";
import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon?: ReactNode;
  accent?: boolean;
}

export function StatCard({ label, value, sub, icon, accent = false }: StatCardProps) {
  return (
    <div className={[styles.card, accent ? styles.accent : ""].join(" ")}>
      {icon && <div className={styles.icon}>{icon}</div>}
      <p className={styles.label}>{label}</p>
      <p className={styles.value}>{value}</p>
      {sub && <p className={styles.sub}>{sub}</p>}
    </div>
  );
}
