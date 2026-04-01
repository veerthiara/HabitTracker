import type { EvidenceItem } from "../../api/types";
import { Badge } from "../ui/Badge";
import styles from "./EvidenceCard.module.css";

const TYPE_COLOR: Record<string, "accent" | "success" | "warning" | "default"> = {
  metric: "accent",
  note:   "warning",
  habit:  "success",
};

interface EvidenceCardProps {
  item: EvidenceItem;
}

export function EvidenceCard({ item }: EvidenceCardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <Badge
          label={item.type}
          color={TYPE_COLOR[item.type] ?? "default"}
        />
        <span className={styles.label}>{item.label}</span>
      </div>
      <p className={styles.value}>{item.value}</p>
    </div>
  );
}
