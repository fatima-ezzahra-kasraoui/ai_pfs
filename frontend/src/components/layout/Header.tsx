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
    <header className="as-header flex h-14 items-center justify-between gap-4 border-b border-line bg-surface px-4">
      <p className="m-0 text-sm text-muted">{current?.label ?? "AgentShield AI"}</p>
      <div className="flex items-center gap-3 text-sm">
        <span className="flex items-center gap-2"><span aria-hidden="true" style={{background:"#e2d5ee",color:"#6d4d91",borderRadius:"50%",width:30,height:30,display:"grid",placeItems:"center",fontWeight:700}}>{user?.username.slice(0,2).toUpperCase()}</span><span>
          {user?.username} <small className="as-role text-muted">({user?.role})</small>
        </span></span>
        <button type="button" onClick={() => void logout()} className="inline-flex items-center gap-1">
          <LogOut aria-hidden="true" size={14} />
          Déconnexion
        </button>
      </div>
    </header>
  );
}
