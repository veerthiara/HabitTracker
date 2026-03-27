import { Card, CardHeader } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import type { Note } from "../../../api/notes";
import styles from "./RecentNotes.module.css";

interface Props {
  notes: Note[];
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function RecentNotes({ notes }: Props) {
  return (
    <Card>
      <CardHeader title="Recent Notes" />
      {notes.length === 0 ? (
        <EmptyState icon="◎" title="No notes yet" message="Start journaling your progress." />
      ) : (
        <ul className={styles.list}>
          {notes.map((note) => (
            <li key={note.id} className={styles.item}>
              <p className={styles.content}>{note.content}</p>
              <span className={styles.time}>{formatRelative(note.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
