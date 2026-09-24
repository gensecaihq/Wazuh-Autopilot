import {
  Activity,
  Bot,
  BookOpen,
  ClipboardCheck,
  FlaskConical,
  HeartPulse,
  KeyRound,
  LayoutDashboard,
  Library,
  Radio,
  ScrollText,
  Settings,
  ShieldCheck,
  Siren,
  Terminal,
  UserCog,
  Users,
  Waypoints,
  Workflow,
  ChartLine,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  perm?: string;
  badgeKey?: "approvals";
}

export const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [{ to: "/", label: "Command Center", icon: LayoutDashboard, perm: "dashboard:read" }],
  },
  {
    section: "Operations",
    items: [
      { to: "/alerts", label: "Alerts", icon: Radio, perm: "alerts:read" },
      { to: "/cases", label: "Incidents", icon: Siren, perm: "cases:read" },
      { to: "/approvals", label: "Approvals", icon: ClipboardCheck, perm: "actions:read", badgeKey: "approvals" },
    ],
  },
  {
    section: "Swarm",
    items: [
      { to: "/agents", label: "Agent Roster", icon: Bot, perm: "agents:read" },
      { to: "/swarm", label: "Swarm Topology", icon: Waypoints, perm: "agents:read" },
      { to: "/skills", label: "Skills Library", icon: Library, perm: "skills:read" },
      { to: "/workflows", label: "Workflows", icon: Workflow, perm: "workflows:read" },
      { to: "/playground", label: "Playground", icon: Terminal, perm: "playground:use" },
      { to: "/evals", label: "Evals", icon: FlaskConical, perm: "evals:read" },
    ],
  },
  {
    section: "Observability",
    items: [
      { to: "/health", label: "Agent Health", icon: HeartPulse, perm: "agents:read" },
      { to: "/runs", label: "Runs & Traces", icon: Activity, perm: "runs:read" },
      { to: "/metrics", label: "Metrics", icon: ChartLine, perm: "runs:read" },
    ],
  },
  {
    section: "Governance",
    items: [
      { to: "/policy", label: "Autonomy Policy", icon: ShieldCheck, perm: "policy:read" },
      { to: "/standards", label: "Standards", icon: BookOpen, perm: "standards:read" },
      { to: "/audit", label: "Audit Log", icon: ScrollText, perm: "audit:read" },
    ],
  },
  {
    section: "Administration",
    items: [
      { to: "/settings", label: "Settings", icon: Settings, perm: "settings:read" },
      { to: "/users", label: "Users", icon: Users, perm: "users:manage" },
      { to: "/roles", label: "Roles & RBAC", icon: UserCog, perm: "users:manage" },
      { to: "/api-tokens", label: "API Tokens", icon: KeyRound, perm: "users:manage" },
    ],
  },
];

