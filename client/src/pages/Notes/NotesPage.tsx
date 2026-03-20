import { TopBar } from "../../components/layout/TopBar";
import { EmptyState } from "../../components/ui/EmptyState";

export function NotesPage() {
  return (
    <>
      <TopBar title="Notes" subtitle="Capture your thoughts" />
      <EmptyState icon="◎" title="Coming in Rev 03" message="Note logging with timestamps." />
    </>
  );
}
