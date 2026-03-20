import styles from "./Badge.module.css";

type Color = "default" | "accent" | "success" | "warning" | "danger";

interface BadgeProps {
  label: string;
  color?: Color;
  dot?: boolean;
}

export function Badge({ label, color = "default", dot = false }: BadgeProps) {
  return (
    <span className={[styles.badge, styles[color]].join(" ")}>
      {dot && <span className={styles.dot} />}
      {label}
    </span>
  );
}
