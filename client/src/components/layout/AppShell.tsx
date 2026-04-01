import { Outlet } from "react-router-dom";
import { ChatPanel } from "../chat/ChatPanel";
import { Sidebar } from "./Sidebar";
import styles from "./AppShell.module.css";

export function AppShell() {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.main}>
        <Outlet />
      </div>
      <ChatPanel />
    </div>
  );
}
