import { LayoutDashboard, Bot, ScanLine, Boxes, Workflow, Radar, TriangleAlert, ClipboardCheck, ScrollText, SlidersHorizontal, Cpu, ChartColumn, Plug, FlaskConical, Code, Users, Settings, type LucideIcon } from "lucide-react";
export interface NavItem { to:string; label:string; icon:LucideIcon; end?:boolean; group:string }
export const NAV_ITEMS: NavItem[] = [
  {to:"/",label:"Vue d'ensemble",icon:LayoutDashboard,group:"OVERVIEW",end:true},
  {to:"/workspace",label:"AI Agent Workspace",icon:Bot,group:"AI WORKSPACE"},
  {to:"/inspector",label:"Security Inspector",icon:ScanLine,group:"AI WORKSPACE"},
  {to:"/agents",label:"Agent Registry",icon:Boxes,group:"AI WORKSPACE"},
  {to:"/executions",label:"Execution Explorer",icon:Workflow,group:"AI WORKSPACE"},
  {to:"/threats",label:"Threat Monitoring",icon:Radar,group:"SECURITY OPERATIONS"},
  {to:"/incidents",label:"Threats & Incidents",icon:TriangleAlert,group:"SECURITY OPERATIONS"},
  {to:"/approvals",label:"Approval Center",icon:ClipboardCheck,group:"SECURITY OPERATIONS"},
  {to:"/audit",label:"Journal d'audit",icon:ScrollText,group:"SECURITY OPERATIONS"},
  {to:"/policies",label:"Security Policies",icon:SlidersHorizontal,group:"AI GOVERNANCE"},
  {to:"/models",label:"Model Management",icon:Cpu,group:"AI GOVERNANCE"},
  {to:"/analytics",label:"Detection Analytics",icon:ChartColumn,group:"AI GOVERNANCE"},
  {to:"/integrations",label:"Integrations",icon:Plug,group:"DEVELOPER"},
  {to:"/lab",label:"Attack Simulation Lab",icon:FlaskConical,group:"DEVELOPER"},
  {to:"/api-docs",label:"API Documentation",icon:Code,group:"DEVELOPER"},
  {to:"/users",label:"Users & Roles",icon:Users,group:"ADMINISTRATION"},
  {to:"/settings",label:"Paramètres",icon:Settings,group:"ADMINISTRATION"},
];
