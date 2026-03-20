import styles from "./Spinner.module.css";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  center?: boolean;
}

export function Spinner({ size = "md", center = false }: SpinnerProps) {
  const el = <span className={[styles.spinner, styles[size]].join(" ")} />;
  return center ? <div className={styles.center}>{el}</div> : el;
}
