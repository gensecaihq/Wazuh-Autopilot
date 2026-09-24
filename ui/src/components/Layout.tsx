import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bell, ChevronDown, Command, LogOut, Menu, Moon, Search, Settings, Sun, User as UserIcon, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useEvents } from "@/lib/events";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/cn";
import { useActions, useSetupStatus } from "@/api/hooks";
import { relTime } from "@/lib/format";
import { Spinner } from "./ui";

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-7 w-7 shrink-0">
        <path d="M8 9 L16 22 L24 9" stroke="rgb(var(--accent))" strokeWidth="2.2" fill="none" strokeLinecap="round" />
        <path d="M8 9 L24 9" stroke="rgb(var(--accent) / .35)" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        <circle cx="8" cy="9" r="3.4" fill="rgb(var(--accent))" />
        <circle cx="24" cy="9" r="3.4" fill="rgb(var(--info))" />
        <circle cx="16" cy="22" r="3.8" fill="rgb(var(--accent))" />
      </svg>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[16px] font-medium tracking-tight">Autopilot</div>
          <div className="text-[10.5px] text-subtle">Agentic SOC · Strands</div>
        </div>
      )}
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const { theme, setTheme } = useTheme();
  const pending = useActions({ status: "proposed" });
  const pendingCount = pending.data?.total ?? 0;

  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pb-2 pt-5">
        <Logo />
      </div>
      <nav className="scrollbar-thin flex-1 overflow-y-auto px-2.5 pb-3">
        {NAV.map((sec) => {
          const items = sec.items.filter((i) => can(i.perm));
          if (!items.length) return null;
          return (
            <div key={sec.section}>
              <div className="section-label">{sec.section}</div>
              <div className="space-y-0.5">
                {items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-2.5 rounded-lg border px-2.5 py-[7px] text-[13.5px] transition",
                        isActive
                          ? "border-line bg-card2 text-fg shadow-[inset_0_1px_0_rgb(255_255_255/0.03)]"
                          : "border-transparent text-muted hover:bg-card2/50 hover:text-fg",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon className={cn("h-[16px] w-[16px] shrink-0", isActive ? "text-accent" : "text-subtle group-hover:text-muted")} />
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.badgeKey === "approvals" && pendingCount > 0 && (
                          <span className="rounded-md border border-accent/30 bg-accent/15 px-1.5 text-[10.5px] font-medium text-accent">
                            {pendingCount}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          );
        })}
      </nav>
      <div className="p-3">
        <div className="grid grid-cols-2 gap-1 rounded-xl border border-line bg-deep/60 p-1">
          <button
            onClick={() => setTheme("light")}
            className={cn("flex items-center justify-center gap-2 rounded-lg py-2 text-sm transition", theme === "light" ? "bg-card2 text-fg ring-1 ring-line" : "text-muted hover:text-fg")}
          >
            <Sun className="h-4 w-4" /> Light
          </button>
          <button
            onClick={() => setTheme("dark")}
            className={cn("flex items-center justify-center gap-2 rounded-lg py-2 text-sm transition", theme === "dark" ? "bg-card2 text-fg ring-1 ring-line" : "text-muted hover:text-fg")}
          >
            <Moon className="h-4 w-4" /> Dark
          </button>
        </div>
      </div>
    </div>
  );
}

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const items = useMemo(() => {
    const all = NAV.flatMap((s) => s.items.filter((i) => can(i.perm)).map((i) => ({ ...i, section: s.section })));
    const needle = q.trim().toLowerCase();
    const found = needle ? all.filter((i) => `${i.label} ${i.section}`.toLowerCase().includes(needle)) : all;
    const extra: { to: string; label: string; section: string }[] = [];
    if (/^inc-\d+/i.test(needle) || /^case/i.test(needle)) extra.push({ to: `/cases?q=${encodeURIComponent(q.trim())}`, label: `Search incidents for “${q.trim()}”`, section: "Search" });
    else if (needle.length > 1) {
      extra.push({ to: `/alerts?q=${encodeURIComponent(q.trim())}`, label: `Search alerts for “${q.trim()}”`, section: "Search" });
      extra.push({ to: `/cases?q=${encodeURIComponent(q.trim())}`, label: `Search incidents for “${q.trim()}”`, section: "Search" });
    }
    return [...found.map((f) => ({ to: f.to, label: f.label, section: f.section, icon: f.icon })), ...extra.map((e) => ({ ...e, icon: Search }))];
  }, [q, can]);

  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);
  useEffect(() => setIdx(0), [q]);

  if (!open) return null;
  const go = (to: string) => {
    navigate(to);
    onClose();
  };
  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center p-4 pt-[12vh]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="card relative w-full max-w-xl overflow-hidden bg-card shadow-2xl">
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Search className="h-4 w-4 text-muted" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIdx((i) => Math.min(items.length - 1, i + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIdx((i) => Math.max(0, i - 1));
              } else if (e.key === "Enter" && items[idx]) go(items[idx].to);
              else if (e.key === "Escape") onClose();
            }}
            placeholder="Jump to a page, search alerts or incidents…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle"
          />
          <span className="kbd">ESC</span>
        </div>
        <div className="scrollbar-thin max-h-[50vh] overflow-y-auto p-1.5">
          {items.length === 0 && <div className="px-3 py-6 text-center text-sm text-muted">No matches</div>}
          {items.map((it, i) => (
            <button
              key={`${it.to}-${i}`}
              onMouseEnter={() => setIdx(i)}
              onClick={() => go(it.to)}
              className={cn("flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm", i === idx ? "bg-card2 text-fg" : "text-muted")}
            >
              <it.icon className={cn("h-4 w-4", i === idx ? "text-accent" : "text-subtle")} />
              <span className="flex-1">{it.label}</span>
              <span className="text-[11px] text-subtle">{it.section}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Notifications() {
  const { events } = useEvents();
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(0);
  const important = events.filter((e) => ["case.created", "action.created", "action.updated", "run.finished"].includes(e.type)).slice(0, 25);
  const unread = important.filter((e) => e.at > seen).length;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button
        className="icon-btn relative"
        aria-label="Notifications"
        onClick={() => {
          setOpen(!open);
          setSeen(Date.now());
        }}
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-accent ring-2 ring-card" />}
      </button>
      {open && (
        <div className="card absolute right-0 top-11 z-50 w-[340px] bg-card shadow-2xl">
          <div className="border-b border-line px-4 py-2.5 text-sm">Notifications</div>
          <div className="scrollbar-thin max-h-[360px] overflow-y-auto">
            {important.length === 0 && <div className="px-4 py-8 text-center text-sm text-muted">You're all caught up.</div>}
            {important.map((e, i) => (
              <div key={i} className="border-b border-line/60 px-4 py-2.5 last:border-0">
                <div className="text-sm">{describeEvent(e.type, e.data)}</div>
                <div className="mt-0.5 text-[11px] text-subtle">{relTime(new Date(e.at).toISOString())}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function describeEvent(type: string, d: Record<string, unknown>): string {
  const s = (k: string) => (typeof d[k] === "string" || typeof d[k] === "number" ? String(d[k]) : "");
  switch (type) {
    case "case.created":
      return `New incident ${s("number")} ${s("title")}`.trim();
    case "case.updated":
      return `Incident ${s("number") || s("id")} updated${s("status") ? ` → ${s("status")}` : ""}`;
    case "action.created":
      return `Action proposed: ${s("label") || s("type")} ${s("target")}`.trim();
    case "action.updated":
      return `Action ${s("label") || s("type")} ${s("status")}`.trim();
    case "run.started":
      return `Run started: ${s("workflow_name") || s("workflow_id") || s("agent_id")}`;
    case "run.finished":
      return `Run ${s("status") || "finished"}: ${s("workflow_name") || s("workflow_id") || s("run_id")}`;
    case "run.step":
      return `${s("agent_id") || "agent"} · ${s("kind") || "step"} ${s("name")}`.trim();
    case "alert.ingested":
      return `Alert: ${s("rule_description") || s("count") + " ingested"}`;
    case "agent.status":
      return `${s("agent_id")} is ${s("status")}`;
    default:
      return type;
  }
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  if (!user) return null;
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2.5 rounded-lg px-1.5 py-1 hover:bg-card2/60">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-card2 text-muted">
          <UserIcon className="h-4 w-4" />
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-[13px]">{user.name}</span>
          <span className="block text-[11px] text-muted">{user.email}</span>
        </span>
        <ChevronDown className="h-4 w-4 text-muted" />
      </button>
      {open && (
        <div className="card absolute right-0 top-12 z-50 w-60 bg-card p-1.5 shadow-2xl">
          <div className="px-2.5 py-2">
            <div className="text-sm">{user.name}</div>
            <div className="text-xs text-muted">{user.email}</div>
            <div className="mt-1.5 inline-flex rounded-md border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[11px] text-accent">{user.role_label}</div>
          </div>
          <div className="my-1 border-t border-line" />
          <button className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-muted hover:bg-card2 hover:text-fg" onClick={() => { setOpen(false); navigate("/account"); }}>
            <UserIcon className="h-4 w-4" /> Account & password
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-muted hover:bg-card2 hover:text-danger"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function Layout() {
  const [mobile, setMobile] = useState(false);
  const [palette, setPalette] = useState(false);
  const { can } = useAuth();
  const { connected } = useEvents();
  const setup = useSetupStatus();
  const navigate = useNavigate();
  const loc = useLocation();

  useEffect(() => setMobile(false), [loc.pathname]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((p) => !p);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  return (
    <div className="flex h-full bg-deep">
      {/* Desktop sidebar */}
      <aside className="hidden w-[236px] shrink-0 border-r border-line bg-bg lg:block">
        <Sidebar />
      </aside>
      {/* Mobile drawer */}
      {mobile && (
        <div className="fixed inset-0 z-[60] lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobile(false)} />
          <aside className="absolute left-0 top-0 h-full w-[260px] border-r border-line bg-bg shadow-2xl">
            <button className="absolute right-3 top-5 text-muted" onClick={() => setMobile(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <Sidebar onNavigate={() => setMobile(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col bg-bg">
        <header className="flex h-[60px] shrink-0 items-center gap-3 border-b border-line px-3 md:px-5">
          <button className="icon-btn lg:hidden" onClick={() => setMobile(true)} aria-label="Open menu">
            <Menu className="h-4 w-4" />
          </button>
          <button
            onClick={() => setPalette(true)}
            className="flex h-9 w-full max-w-[300px] items-center gap-2 rounded-lg border border-line bg-deep/40 px-3 text-sm text-subtle hover:border-subtle/50"
          >
            <Search className="h-4 w-4" />
            <span className="flex-1 text-left">Search here…</span>
            <span className="flex items-center gap-0.5 rounded border border-line bg-card2 px-1.5 py-0.5 text-[10px] text-muted">
              <Command className="h-3 w-3" />K
            </span>
          </button>
          <div className="flex-1" />
          {setup.data?.demo_mode && (
            <span className="hidden rounded-md border border-info/30 bg-info/10 px-2 py-1 text-[11px] text-info md:inline">Demo mode</span>
          )}
          <span className="hidden items-center gap-1.5 text-[11px] text-muted md:flex" title={connected ? "Live updates connected" : "Live updates disconnected"}>
            <span className={cn("h-1.5 w-1.5 rounded-full", connected ? "bg-success" : "bg-subtle")} />
            {connected ? "Live" : "Offline"}
          </span>
          <UserMenu />
          <div className="mx-1 hidden h-6 w-px bg-line sm:block" />
          {can("settings:read") && (
            <button className="icon-btn" onClick={() => navigate("/settings")} aria-label="Settings">
              <Settings className="h-4 w-4" />
            </button>
          )}
          <Notifications />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Suspense
            fallback={
              <div className="flex h-64 items-center justify-center">
                <Spinner className="h-5 w-5" />
              </div>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}
