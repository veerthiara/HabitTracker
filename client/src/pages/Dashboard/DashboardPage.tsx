import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../../api/dashboard";
import { useChat } from "../../context/ChatContext";
import { TopBar } from "../../components/layout/TopBar";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { SummaryCards } from "./components/SummaryCards";
import { HabitsToday } from "./components/HabitsToday";
import { HydrationBar } from "./components/HydrationBar";
import { RecentNotes } from "./components/RecentNotes";
import styles from "./DashboardPage.module.css";

function todayISO() {
  return new Date().toISOString().split("T")[0];
}

export function DashboardPage() {
  const today = todayISO();
  const { togglePanel } = useChat();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", today],
    queryFn: () => dashboardApi.summary(today),
    staleTime: 30_000,
  });

  return (
    <>
      <TopBar
        title="Dashboard"
        subtitle={new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
        action={
          <Button variant="primary" onClick={togglePanel}>
            ◐ Ask AI
          </Button>
        }
      />
      <div className={styles.content}>
        {isLoading && <Spinner center />}
        {isError && <p className={styles.error}>Failed to load dashboard. Is the backend running?</p>}
        {data && (
          <>
            <SummaryCards data={data} />
            <div className={styles.grid}>
              <div className={styles.col}>
                <HabitsToday summaries={data.habit_summaries} today={today} />
              </div>
              <div className={styles.col}>
                <HydrationBar totalMl={data.hydration_today_ml} />
                <RecentNotes notes={data.recent_notes} />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
