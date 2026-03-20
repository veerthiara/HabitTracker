import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { TopBar } from "../../components/layout/TopBar";
import { Card, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { notesApi, type Note } from "../../api/notes";
import styles from "./NotesPage.module.css";

function relativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function NotesPage() {
  const qc = useQueryClient();
  const [content, setContent] = useState("");

  const { data: notes, isLoading } = useQuery({
    queryKey: ["notes"],
    queryFn: notesApi.list,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: () => notesApi.create({ content: content.trim(), source: "manual" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setContent("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => notesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && content.trim()) {
      createMutation.mutate();
    }
  }

  return (
    <>
      <TopBar title="Notes" subtitle="Capture your thoughts" />
      <div className={styles.content}>
        {/* Compose */}
        <Card>
          <CardHeader title="New Note" subtitle="⌘↵ to save" />
          <textarea
            className={styles.textarea}
            placeholder="Write something..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={4}
          />
          <div className={styles.actions}>
            <Button
              onClick={() => createMutation.mutate()}
              loading={createMutation.isPending}
              disabled={!content.trim()}
            >
              Save Note
            </Button>
          </div>
        </Card>

        {/* List */}
        <Card>
          <CardHeader title="All Notes" />
          {isLoading && <Spinner center />}
          {!isLoading && (!notes || notes.length === 0) && (
            <EmptyState icon="◎" title="No notes yet" message="Save your first note above." />
          )}
          {notes && notes.length > 0 && (
            <ul className={styles.noteList}>
              {notes.map((note: Note) => (
                <li key={note.id} className={styles.noteItem}>
                  <p className={styles.noteContent}>{note.content}</p>
                  <div className={styles.noteMeta}>
                    <span className={styles.noteTime}>{relativeTime(note.created_at)}</span>
                    <button
                      className={styles.deleteBtn}
                      onClick={() => deleteMutation.mutate(note.id)}
                      disabled={deleteMutation.isPending}
                      aria-label="Delete note"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
