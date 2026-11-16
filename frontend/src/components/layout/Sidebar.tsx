import { PanelLeftClose, PanelLeftOpen, ShieldCheck } from "lucide-react";
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
    <div className={cn("flex shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-150", collapsed ? "w-16" : "w-60")}>
      <div className="flex h-14 items-center gap-2 border-b border-line px-4">
        <ShieldCheck aria-hidden="true" className="shrink-0 text-primary" size={22} />
        {!collapsed && <strong className="truncate">AgentShield AI</strong>}
      </div>
      <nav aria-label="Navigation principale" className="flex flex-1 flex-col gap-1 p-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            title={collapsed ? label : undefined}
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
