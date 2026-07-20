import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import ChangePassword from "./ChangePassword";
import CommandPalette from "./CommandPalette";

// Consistent line icons (single stroke family) — replaces the mismatched
// unicode glyphs for a cleaner, more legible nav.
function Icon({ name }: { name: string }): ReactNode {
  const p: Record<string, ReactNode> = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7.5" height="8" rx="1.5" />
        <rect x="13.5" y="3" width="7.5" height="5" rx="1.5" />
        <rect x="13.5" y="11" width="7.5" height="10" rx="1.5" />
        <rect x="3" y="14" width="7.5" height="7" rx="1.5" />
      </>
    ),
    target: (
      <>
        <circle cx="12" cy="12" r="8.5" />
        <circle cx="12" cy="12" r="4.5" />
        <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
      </>
    ),
    mail: (
      <>
        <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
        <path d="m3.5 7 8.5 6 8.5-6" />
      </>
    ),
    page: (
      <>
        <rect x="3" y="4.5" width="18" height="15" rx="2" />
        <path d="M3 9h18" />
      </>
    ),
    users: (
      <>
        <circle cx="9" cy="8" r="3.2" />
        <path d="M2.8 19a6.2 6.2 0 0 1 12.4 0" />
        <path d="M16.4 5.3a3.2 3.2 0 0 1 0 6" />
        <path d="M18 19a6 6 0 0 0-2.6-4.9" />
      </>
    ),
    server: (
      <>
        <rect x="3" y="4" width="18" height="7" rx="2" />
        <rect x="3" y="13" width="18" height="7" rx="2" />
        <path d="M7 7.5h.01" />
        <path d="M7 16.5h.01" />
      </>
    ),
    webhook: (
      <>
        <path d="M9.5 14.5 14.5 9.5" />
        <path d="M11 6.5 12.5 5a4 4 0 0 1 5.7 5.7L16.7 12" />
        <path d="M13 17.5 11.5 19a4 4 0 0 1-5.7-5.7L7.3 12" />
      </>
    ),
    key: (
      <>
        <circle cx="7.5" cy="15.5" r="3.3" />
        <path d="m10 13 7.5-7.5" />
        <path d="m14.5 6.5 2 2" />
        <path d="m17 4 3 3" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="3.6" />
        <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
      </>
    ),
    book: (
      <>
        <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
        <path d="M4 19a2 2 0 0 1 2-2h13" />
      </>
    ),
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {p[name]}
    </svg>
  );
}

const NAV = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/campaigns", label: "Campaigns", icon: "target" },
  { to: "/templates", label: "Email Templates", icon: "mail" },
  { to: "/pages", label: "Landing Pages", icon: "page" },
  { to: "/groups", label: "Groups & Targets", icon: "users" },
  { to: "/profiles", label: "Sending Profiles", icon: "server" },
  { to: "/webhooks", label: "Webhooks", icon: "webhook", adminOnly: true },
  { to: "/apikeys", label: "API Keys", icon: "key" },
  { to: "/users", label: "Users", icon: "user", adminOnly: true },
  { to: "/docs", label: "Documentation", icon: "book" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [pwOpen, setPwOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("phishsim-sidebar") === "1");
  const location = useLocation();

  useEffect(() => {
    localStorage.setItem("phishsim-sidebar", collapsed ? "1" : "0");
  }, [collapsed]);

  // Scroll the content area to top on route change.
  useEffect(() => {
    document.querySelector(".main")?.scrollTo({ top: 0, behavior: "smooth" });
  }, [location.pathname]);

  return (
    <div className={`app${collapsed ? " collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-img" src="/logo.png" alt="VoltPhish" />
        </div>
        {NAV.filter((n) => !n.adminOnly || user?.role === "admin").map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            title={n.label}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            <span className="nav-ico"><Icon name={n.icon} /></span>
            <span className="nav-label">{n.label}</span>
          </NavLink>
        ))}
        <div className="sidebar-foot">
          <button
            className="collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "»" : "«"}
          </button>
          <div className="user-card">
            <div className="avatar">{(user?.email?.slice(0, 2) || "?").toUpperCase()}</div>
            <div className="user-meta">
              <div className="user-email" title={user?.email}>{user?.email}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
          <button className="foot-btn" onClick={toggle}>
            <span className="foot-ico">{theme === "dark" ? "☀️" : "🌙"}</span>
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <div className="foot-row">
            <button className="foot-btn" onClick={() => setPwOpen(true)}>
              <span className="foot-ico">🔑</span>Password
            </button>
            <button className="foot-btn danger" onClick={() => logout()}>
              <span className="foot-ico">⎋</span>Sign out
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <div className="page-fade" key={location.pathname}>
          <Outlet />
        </div>
      </main>
      {pwOpen && <ChangePassword onClose={() => setPwOpen(false)} />}
      <CommandPalette />
    </div>
  );
}
