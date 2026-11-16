import { ChartColumn, ClipboardCheck, FlaskConical, LayoutDashboard, Radar, ScrollText, Settings, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

/** Les 7 routes protégées de l'application (source unique pour la Sidebar et le Header). */
export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Vue d'ensemble", icon: LayoutDashboard, end: true },
  { to: "/lab", label: "Attack Simulation Lab", icon: FlaskConical },
  { to: "/threats", label: "Threat Monitoring", icon: Radar },
  { to: "/approvals", label: "Approval Center", icon: ClipboardCheck },
  { to: "/analytics", label: "Detection Analytics", icon: ChartColumn },
  { to: "/audit", label: "Journal d'audit", icon: ScrollText },
  { to: "/settings", label: "Paramètres", icon: Settings },
];
