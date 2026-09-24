import {
  Microscope,
  Globe,
  ClipboardList,
  Hammer,
  ServerCog,
  Activity,
  BadgeCheck,
  Bot,
  Brain,
  Bug,
  ClipboardCheck,
  Crosshair,
  Crown,
  Eye,
  FileChartColumn,
  FileCode,
  Fingerprint,
  GitMerge,
  Network,
  Radar,
  RadioTower,
  Scale,
  ScanSearch,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldHalf,
  Siren,
  Swords,
  Target,
  Users,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";

const ICONS: Record<string, LucideIcon> = {
  "shield-alert": ShieldAlert,
  "shield-check": ShieldCheck,
  "shield-half": ShieldHalf,
  "git-merge": GitMerge,
  search: Search,
  "scan-search": ScanSearch,
  radar: Radar,
  crosshair: Crosshair,
  bug: Bug,
  target: Target,
  zap: Zap,
  wrench: Wrench,
  "file-code": FileCode,
  scale: Scale,
  "file-bar-chart": FileChartColumn,
  "file-chart-column": FileChartColumn,
  brain: Brain,
  network: Network,
  eye: Eye,
  siren: Siren,
  fingerprint: Fingerprint,
  activity: Activity,
  "radio-tower": RadioTower,
  crown: Crown,
  users: Users,
  swords: Swords,
  "badge-check": BadgeCheck,
  "clipboard-check": ClipboardCheck,
  bot: Bot,
  microscope: Microscope,
  globe: Globe,
  "clipboard-list": ClipboardList,
  hammer: Hammer,
  "server-cog": ServerCog,
};

export function iconFor(name: string | undefined): LucideIcon {
  return (name && ICONS[name]) || Bot;
}

export function AgentAvatar({
  icon,
  color,
  size = "md",
  running,
}: {
  icon?: string;
  color?: string;
  size?: "sm" | "md" | "lg";
  running?: boolean;
}) {
  const Icon = iconFor(icon);
  const c = color || "#ff8127";
  const dims = { sm: "h-7 w-7", md: "h-10 w-10", lg: "h-14 w-14" }[size];
  const ic = { sm: "h-3.5 w-3.5", md: "h-5 w-5", lg: "h-7 w-7" }[size];
  return (
    <div
      className={cn("relative flex shrink-0 items-center justify-center rounded-xl border", dims, running && "animate-pulseRing")}
      style={{ color: c, borderColor: `${c}40`, background: `${c}14`, boxShadow: `0 0 22px -8px ${c}` }}
    >
      <Icon className={ic} />
    </div>
  );
}
