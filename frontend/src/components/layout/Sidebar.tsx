import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "../../lib/utils";
import { NAV_ITEMS } from "./navigation";

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

/** Barre latérale réductible. Réduite, les libellés restent disponibles (lecteurs d'écran, info-bulle). */
export function Sidebar({ collapsed, onToggle }: Props) {
  return (
    <div className={cn("as-sidebar flex shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-150", collapsed ? "w-16" : "w-60")}>
      <div className="flex h-14 items-center gap-2 border-b border-line px-4">
        <svg aria-hidden="true" width="30" height="30" viewBox="0 0 100 100" className="shrink-0"><rect x="10" y="10" width="56" height="56" rx="12" fill="#a88bc4"/><rect x="34" y="34" width="56" height="56" rx="12" fill="#6d4d91"/><rect x="34" y="34" width="32" height="32" rx="6" fill="#e2d5ee"/></svg>
        {!collapsed && <strong className="as-brand-name truncate" style={{fontSize:17,letterSpacing:"-.5px"}}>AgentShield AI</strong>}
      </div>
      <nav aria-label="Navigation principale" className="flex flex-1 flex-col gap-1 p-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end, group }, index) => (
          <div key={to}>
          {!collapsed && (index === 0 || NAV_ITEMS[index-1].group !== group) && <div className="as-nav-group">{group}</div>}
          <NavLink
            key={to}
            to={to}
            end={end}
            title={label}
            aria-label={label}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm no-underline text-fg hover:bg-bg",
                isActive && "bg-bg font-semibold text-primary",
                collapsed && "justify-center px-0",
              )
            }
          >
            <Icon aria-hidden="true" className="shrink-0" size={18} />
            <span className={cn(collapsed && "sr-only")}>{label}</span>
          </NavLink>
          </div>
        ))}
      </nav>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={!collapsed}
        aria-label={collapsed ? "Développer le menu" : "Réduire le menu"}
        className="m-2 flex items-center justify-center gap-2 border-line text-sm"
      >
        {collapsed ? <PanelLeftOpen aria-hidden="true" size={18} /> : <PanelLeftClose aria-hidden="true" size={18} />}
        {!collapsed && <span>Réduire</span>}
      </button>
    </div>
  );
}
