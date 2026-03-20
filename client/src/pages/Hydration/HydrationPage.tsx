import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { TopBar } from "../../components/layout/TopBar";
import { Card, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { bottleEventsApi, type BottleEvent } from "../../api/bottleEvents";
import styles from "./HydrationPage.module.css";

const DAILY_GOAL_ML = 2000;

function todayISO() {
  return new Date().toISOString().split("T")[0];
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatVolume(ml: number) {
  return ml >= 1000 ? `${(ml / 1000).toFixed(1)} L` : `${ml} ml`;
}

export function HydrationPage() {
  const today = todayISO();
  const qc = useQueryClient();
  const [volume, setVolume] = useState("250");
  const [note, setNote] = useState("");

  const { data: events, isLoading } = useQuery({
    queryKey: ["bottle-events", today],
    queryFn: () => bottleEventsApi.list(today),
    staleTime: 30_000,
  });

  const addMutation = useMutation({
    mutationFn: () =>
      bottleEventsApi.create({
        event_ts: new Date().toISOString(),
        volume_ml: Math.max(1, parseInt(volume, 10) || 250),
        notes: note.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bottle-events", today] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setNote("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => bottleEventsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bottle-events", today] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const totalMl = events?.reduce((sum, e) => sum + e.volume_ml, 0) ?? 0;
  const pct = Math.min(100, Math.round((totalMl / DAILY_GOAL_ML) * 100));
  const barColor =
    pct >= 100 ? styles.barFull : pct >= 60 ? styles.barGood : pct >= 30 ? styles.barWarning : styles.barLow;

  const quickOptions = [150, 250, 350, 500];

  return (
    <>
      <TopBar title="Hydration" subtitle="Track your daily water intake" />
      <div className={styles.content}>
        {/* Progress */}
        <Card className={styles.progressCard}>
          <CardHeader title="Today's Progress" subtitle={`Goal: ${formatVolume(DAILY_GOAL_ML)}`} />
          <div className={styles.statsRow}>
            <span className={styles.totalLabel}>{formatVolume(totalMl)}</span>
            <span className={styles.pctLabel}>{pct}%</span>
          </div>
          <div className={styles.barTrack}>
            <div className={`${styles.barFill} ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
        </Card>

        {/* Add form */}
        <Card className={styles.addCard}>
          <CardHeader title="Log Water" />
          <div className={styles.quickRow}>
            {quickOptions.map((ml) => (
              <button
                key={ml}
                className={`${styles.quickBtn} ${volume === String(ml) ? styles.quickBtnActive : ""}`}
                onClick={() => setVolume(String(ml))}
                type="button"
              >
                {ml} ml
              </button>
            ))}
          </div>
          <div className={styles.formRow}>
            <div className={styles.inputGroup}>
              <label htmlFor="volume-input" className={styles.inputLabel}>
                Volume (ml)
              </label>
              <input
                id="volume-input"
                type="number"
                min={1}
                step={50}
                className={styles.input}
                value={volume}
                onChange={(e) => setVolume(e.target.value)}
              />
            </div>
            <div className={styles.inputGroup} style={{ flex: 2 }}>
              <label htmlFor="note-input" className={styles.inputLabel}>
                Note (optional)
              </label>
              <input
                id="note-input"
                type="text"
                className={styles.input}
                placeholder="e.g. with lemon"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            <Button
              onClick={() => addMutation.mutate()}
              loading={addMutation.isPending}
              disabled={!volume || parseInt(volume, 10) <= 0}
            >
              + Log
            </Button>
          </div>
        </Card>

        {/* Event list */}
        <Card>
          <CardHeader title="Today's Logs" />
          {isLoading && <Spinner center />}
          {!isLoading && (!events || events.length === 0) && (
            <EmptyState icon="◉" title="No entries yet" message="Log your first glass of water above." />
          )}
          {events && events.length > 0 && (
            <ul className={styles.eventList}>
              {[...events].reverse().map((ev: BottleEvent) => (
                <li key={ev.id} className={styles.eventItem}>
                  <span className={styles.eventTime}>{formatTime(ev.event_ts)}</span>
                  <span className={styles.eventVolume}>{formatVolume(ev.volume_ml)}</span>
                  {ev.notes && <span className={styles.eventNote}>{ev.notes}</span>}
                  <button
                    className={styles.deleteBtn}
                    onClick={() => deleteMutation.mutate(ev.id)}
                    disabled={deleteMutation.isPending}
                    aria-label="Delete"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
