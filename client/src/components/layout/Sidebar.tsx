import { NavLink } from "react-router-dom";
import styles from "./Sidebar.module.css";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",          label: "Dashboard",  icon: "◈" },
  { to: "/habits",    label: "Habits",     icon: "✓" },
  { to: "/hydration", label: "Hydration",  icon: "◉" },
  { to: "/notes",     label: "Notes",      icon: "◎" },
];

export function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoMark}>Ht</span>
        <span className={styles.logoText}>HabitTracker</span>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              [styles.navItem, isActive ? styles.active : ""].join(" ")
            }
          >
            <span className={styles.navIcon}>{item.icon}</span>
            <span className={styles.navLabel}>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.footer}>
        <div className={styles.userAvatar}>V</div>
        <div className={styles.userInfo}>
          <p className={styles.userName}>Demo User</p>
          <p className={styles.userRole}>Local dev</p>
        </div>
      </div>
    </aside>
  );
}
