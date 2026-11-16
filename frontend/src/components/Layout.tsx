import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const LINKS = [
  { to: "/", label: "Vue d'ensemble", end: true },
  { to: "/audit", label: "Journal d'audit" },
  { to: "/analytics", label: "Detection Analytics" },
  { to: "/settings", label: "Paramètres" },
];

/** Mise en page minimale. Le design system d'É3 (AS-S1-007) la remplacera. */
export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <a className="skip" href="#main">
        Aller au contenu
      </a>
      <header className="topbar">
        <strong>AgentShield AI</strong>
        <nav aria-label="Navigation principale">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <span className="who">
          {user?.username} <small>({user?.role})</small>
          <button type="button" onClick={() => void logout()}>
            Déconnexion
          </button>
        </span>
      </header>
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
