import { LogOut } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { NAV_ITEMS } from "./navigation";

/** En-tête : section courante, identité (venant de /api/auth/me) et déconnexion. */
export function Header() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const current = NAV_ITEMS.find((i) => (i.end ? pathname === i.to : pathname.startsWith(i.to)));
  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b border-line bg-surface px-4">
      <p className="m-0 text-sm text-muted">{current?.label ?? "AgentShield AI"}</p>
      <div className="flex items-center gap-3 text-sm">
        <span>
          {user?.username} <small className="text-muted">({user?.role})</small>
        </span>
        <button type="button" onClick={() => void logout()} className="inline-flex items-center gap-1">
          <LogOut aria-hidden="true" size={14} />
          Déconnexion
        </button>
      </div>
    </header>
  );
}
