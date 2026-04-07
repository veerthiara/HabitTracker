import { useChat } from "../../context/ChatContext";
import type { ChatMessage as ChatMessageType } from "../../context/ChatContext";
import { Badge } from "../ui/Badge";
import styles from "./ChatMessage.module.css";

interface ChatMessageProps {
  message: ChatMessageType;
}

const INTENT_LABELS: Record<string, string> = {
  bottle_activity:      "Hydration",
  habit_summary:        "Habits",
  note_pattern_question:"Notes",
  general_question:     "General",
  unsupported:          "—",
};

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const { showEvidence, selectedMessageId } = useChat();

  return (
    <div className={[styles.row, isUser ? styles.user : styles.assistant].join(" ")}>
      <div className={styles.bubble}>
        <p className={styles.text}>{message.content}</p>

        {!isUser && !message.error && message.intent && message.intent !== "unsupported" && (
          <div className={styles.meta}>
            <Badge
              label={INTENT_LABELS[message.intent] ?? message.intent}
              color="accent"
              dot
            />
            {message.used_notes && (
              <Badge label="Semantic search" color="warning" dot />
            )}
          </div>
        )}

        {!isUser && message.error && (
          <div className={styles.meta}>
            <Badge label="Error" color="danger" dot />
          </div>
        )}

        {!isUser && !message.error && (message.evidence?.length ?? 0) > 0 && (
          <button
            className={styles.evidenceBtn}
            onClick={() => showEvidence(message.id)}
          >
            {selectedMessageId === message.id
              ? "Hide Evidence"
              : `View Evidence (${message.evidence!.length})`}
          </button>
        )}
      </div>
    </div>
  );
}
