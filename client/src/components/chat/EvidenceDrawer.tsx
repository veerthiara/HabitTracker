import { useChat } from "../../context/ChatContext";
import { Badge } from "../ui/Badge";
import { EvidenceCard } from "./EvidenceCard";
import styles from "./EvidenceDrawer.module.css";

/**
 * EvidenceDrawer — secondary slide-in panel showing the evidence items
 * for the currently selected assistant message.
 *
 * Positioning: fixed, sits immediately to the LEFT of the ChatPanel
 * (right: 420px when visible). Both panels are visible side-by-side.
 */
export function EvidenceDrawer() {
  const { messages, selectedMessageId, hideEvidence } = useChat();

  const selectedMessage = selectedMessageId
    ? messages.find((m) => m.id === selectedMessageId)
    : null;

  const isOpen = !!selectedMessage;
  const evidence = selectedMessage?.evidence ?? [];

  return (
    <aside className={[styles.drawer, isOpen ? styles.open : ""].join(" ")}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.headerIcon}>◎</span>
          <p className={styles.headerTitle}>Evidence</p>
        </div>
        <button className={styles.closeBtn} onClick={hideEvidence} title="Close">
          ✕
        </button>
      </div>

      <div className={styles.body}>
        {selectedMessage?.used_notes && (
          <div className={styles.noticeRow}>
            <Badge label="Semantic search used" color="warning" dot />
            <p className={styles.noticeText}>
              Answer includes insights from your notes.
            </p>
          </div>
        )}

        {evidence.length === 0 ? (
          <div className={styles.empty}>
            <p>No structured evidence for this answer.</p>
          </div>
        ) : (
          <div className={styles.list}>
            {evidence.map((item, i) => (
              <EvidenceCard key={i} item={item} />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
