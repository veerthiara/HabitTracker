import { TopBar } from "../../components/layout/TopBar";
import { EmptyState } from "../../components/ui/EmptyState";

export function HabitsPage() {
  return (
    <>
      <TopBar title="Habits" subtitle="Manage your daily habits" />
      <EmptyState icon="✓" title="Coming in Rev 03" message="Full habit management with streaks and log history." />
    </>
  );
}
