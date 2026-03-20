import { TopBar } from "../../components/layout/TopBar";
import { EmptyState } from "../../components/ui/EmptyState";

export function HydrationPage() {
  return (
    <>
      <TopBar title="Hydration" subtitle="Log your water intake" />
      <EmptyState icon="◉" title="Coming in Rev 03" message="Bottle event logging with daily progress bar." />
    </>
  );
}
