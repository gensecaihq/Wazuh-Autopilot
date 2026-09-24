import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, ChevronsUpDown, Inbox, Loader2, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/api/client";

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------
export function Card({ className, children, glow }: { className?: string; children: ReactNode; glow?: boolean }) {
  return <div className={cn("card", glow && "card-glow", className)}>{children}</div>;
}

export function CardHeader({
  title,
  subtitle,
  right,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-3 px-5 pt-4", className)}>
      <div className="min-w-0">
        <h3 className="text-[15px] font-normal text-fg">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, right }: { title: ReactNode; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-4 md:px-6">
      <div className="min-w-0">
        <h1 className="text-[22px] font-normal tracking-tight text-fg md:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("space-y-4 p-4 md:p-6", className)}>{children}</div>;
}

// ---------------------------------------------------------------------------
// Badges & chips
// ---------------------------------------------------------------------------
type Tone = "neutral" | "accent" | "danger" | "success" | "info" | "warn";

const toneCls: Record<Tone, string> = {
  neutral: "border-line bg-card2 text-muted",
  accent: "border-accent/30 bg-accent/10 text-accent",
  danger: "border-danger/30 bg-danger/10 text-danger",
  success: "border-success/30 bg-success/10 text-success",
  info: "border-info/30 bg-info/10 text-info",
  warn: "border-warn/30 bg-warn/10 text-warn",
};

export function Badge({ tone = "neutral", children, className, dot }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium", toneCls[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

const severityTone: Record<string, Tone> = {
  critical: "danger",
  high: "accent",
  medium: "warn",
  low: "info",
  informational: "neutral",
};

export function SeverityBadge({ value }: { value: string }) {
  return (
    <Badge tone={severityTone[value] ?? "neutral"} dot>
      {value === "informational" ? "info" : value}
    </Badge>
  );
}

export const riskTone = severityTone;

const statusTone: Record<string, Tone> = {
  // cases
  open: "danger",
  triage: "accent",
  investigating: "info",
  contained: "warn",
  resolved: "success",
  closed: "neutral",
  false_positive: "neutral",
  // actions
  proposed: "accent",
  approved: "info",
  rejected: "neutral",
  executing: "info",
  executed: "success",
  verified: "success",
  failed: "danger",
  rolled_back: "warn",
  expired: "neutral",
  // runs
  queued: "neutral",
  running: "accent",
  completed: "success",
  cancelled: "neutral",
  // alerts
  new: "accent",
  triaged: "info",
  grouped: "neutral",
  suppressed: "neutral",
  // health
  healthy: "success",
  degraded: "warn",
  down: "danger",
  unknown: "neutral",
  idle: "neutral",
  error: "danger",
  disabled: "neutral",
  ok: "success",
  blocked: "warn",
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <Badge tone={statusTone[value] ?? "neutral"} dot>
      {value.replace(/_/g, " ")}
    </Badge>
  );
}

export function statusColor(value: string): string {
  const t = statusTone[value] ?? "neutral";
  return { neutral: "bg-subtle", accent: "bg-accent", danger: "bg-danger", success: "bg-success", info: "bg-info", warn: "bg-warn" }[t];
}

export function StatusDot({ value, pulse }: { value: string; pulse?: boolean }) {
  return (
    <span className="relative inline-flex h-2 w-2">
      {pulse && <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", statusColor(value))} />}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", statusColor(value))} />
    </span>
  );
}

/** Delta chip like the design: "25.6% ↓". `goodWhenDown` flips colors (e.g. incidents). */
export function DeltaChip({ value, goodWhenDown = false }: { value: number; goodWhenDown?: boolean }) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const up = value > 0;
  const flat = value === 0;
  const good = flat ? null : goodWhenDown ? !up : up;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md border px-1.5 py-px text-[11px]",
        good === null && "border-line bg-card2 text-muted",
        good === true && "border-line bg-card2 text-fg/80",
        good === false && "border-danger/30 bg-danger/10 text-danger",
      )}
    >
      {Math.abs(value).toFixed(1)}%{!flat && (up ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Segmented control & tabs
// ---------------------------------------------------------------------------
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
  size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-deep/50 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md transition",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm",
            value === o.value ? "bg-card2 text-fg shadow-sm ring-1 ring-line" : "text-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({
  value,
  onChange,
  tabs,
}: {
  value: T;
  onChange: (v: T) => void;
  tabs: { value: T; label: ReactNode; count?: number }[];
}) {
  return (
    <div className="scrollbar-thin flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition",
            value === t.value ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="rounded bg-card2 px-1.5 text-[10px] text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overlays
// ---------------------------------------------------------------------------
function useEsc(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  width = "max-w-lg",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEsc(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div role="dialog" aria-modal className={cn("card relative flex max-h-[90vh] w-full flex-col bg-card shadow-2xl", width)}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h3 className="text-base font-normal">{title}</h3>
          <button className="text-muted hover:text-fg" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="scrollbar-thin overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = "max-w-2xl",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEsc(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[70] flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />
      <aside className={cn("relative flex h-full w-full flex-col border-l border-line bg-card shadow-2xl", width)}>
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h3 className="truncate text-base font-normal">{title}</h3>
            {subtitle && <div className="mt-0.5 text-xs text-muted">{subtitle}</div>}
          </div>
          <button className="icon-btn h-8 w-8" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </aside>
    </div>,
    document.body,
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel = "Confirm",
  tone = "primary",
  requireReason,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  tone?: "primary" | "danger" | "success";
  requireReason?: string;
  loading?: boolean;
}) {
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open) setReason("");
  }, [open]);
  const cls = tone === "danger" ? "btn-danger" : tone === "success" ? "btn-success" : "btn-primary";
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className={cls} disabled={loading || (!!requireReason && !reason.trim())} onClick={() => onConfirm(reason.trim())}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </button>
        </>
      }
    >
      {body && <div className="text-sm text-muted">{body}</div>}
      {requireReason !== undefined && (
        <div className="mt-3">
          <label className="label">{requireReason}</label>
          <textarea className="textarea" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
        </div>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin text-muted", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4", className)} />;
}

export function SkeletonRows({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2.5 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={cn("h-8", i % 3 === 2 ? "w-4/5" : "w-full")} />
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-card2 text-muted">
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <div className="text-sm font-medium">{title}</div>
      {body && <div className="mt-1 max-w-sm text-sm text-muted">{body}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-danger">
        <TriangleAlert className="h-5 w-5" />
      </div>
      <div className="text-sm font-medium">Couldn't load this</div>
      <div className="mt-1 max-w-md break-words text-sm text-muted">{errorMessage(error)}</div>
      {onRetry && (
        <button className="btn-secondary btn-sm mt-4" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

/** Wraps a react-query result with loading/error/empty handling. */
export function Async<D>({
  q,
  children,
  empty,
  isEmpty,
  loading,
}: {
  q: { data: D | undefined; isLoading: boolean; error: unknown; refetch: () => unknown };
  children: (d: D) => ReactNode;
  empty?: ReactNode;
  isEmpty?: (d: D) => boolean;
  loading?: ReactNode;
}) {
  if (q.isLoading) return <>{loading ?? <SkeletonRows />}</>;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.data === undefined) return <>{empty ?? <EmptyState title="Nothing here yet" />}</>;
  if (isEmpty?.(q.data)) return <>{empty ?? <EmptyState title="Nothing here yet" />}</>;
  return <>{children(q.data)}</>;
}

// ---------------------------------------------------------------------------
// Table with sorting
// ---------------------------------------------------------------------------
export interface Column<R> {
  key: string;
  header: ReactNode;
  cell: (r: R) => ReactNode;
  sort?: (r: R) => string | number | null | undefined;
  className?: string;
  headerClassName?: string;
}

export function DataTable<R>({
  rows,
  columns,
  rowKey,
  onRowClick,
  initialSort,
  empty,
  dense,
}: {
  rows: R[];
  columns: Column<R>[];
  rowKey: (r: R) => string;
  onRowClick?: (r: R) => void;
  initialSort?: { key: string; dir: "asc" | "desc" };
  empty?: ReactNode;
  dense?: boolean;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sort) return rows;
    const get = col.sort;
    return [...rows].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const r = va < vb ? -1 : 1;
      return sort.dir === "asc" ? r : -r;
    });
  }, [rows, sort, columns]);

  if (!rows.length) return <>{empty ?? <EmptyState title="No results" body="Try adjusting filters." />}</>;

  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse">
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th key={c.key} className={cn("th", c.headerClassName)}>
                {c.sort ? (
                  <button
                    className="inline-flex items-center gap-1 hover:text-fg"
                    onClick={() =>
                      setSort((s) => (s?.key === c.key ? { key: c.key, dir: s.dir === "asc" ? "desc" : "asc" } : { key: c.key, dir: "desc" }))
                    }
                  >
                    {c.header}
                    {sort?.key === c.key ? (
                      sort.dir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      )
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-50" />
                    )}
                  </button>
                ) : (
                  c.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={rowKey(r)}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={cn("border-b border-line/60 last:border-0", onRowClick && "cursor-pointer hover:bg-card2/60")}
            >
              {columns.map((c) => (
                <td key={c.key} className={cn("td", dense && "py-2", c.className)}>
                  {c.cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Content renderers
// ---------------------------------------------------------------------------
export function Markdown({ children, className }: { children: string | null | undefined; className?: string }) {
  if (!children) return <p className="text-sm text-muted">No content.</p>;
  return (
    <div className={cn("markdown", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

export function JsonView({ value, collapsed = false, maxHeight = "max-h-[480px]" }: { value: unknown; collapsed?: boolean; maxHeight?: string }) {
  const [open, setOpen] = useState(!collapsed);
  const text = useMemo(() => {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }, [value]);
  return (
    <div className="rounded-lg border border-line bg-deep">
      <button className="flex w-full items-center gap-1 px-3 py-1.5 text-left text-[11px] text-muted hover:text-fg" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        JSON · {text.length.toLocaleString()} chars
      </button>
      {open && (
        <pre className={cn("scrollbar-thin overflow-auto border-t border-line px-3 py-2 font-mono text-[11.5px] leading-relaxed text-fg/85", maxHeight)}>
          {text}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Form controls
// ---------------------------------------------------------------------------
export function Field({ label, hint, children, className }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <label className="label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-subtle">{hint}</p>}
    </div>
  );
}

export function Toggle({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label?: ReactNode }) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-2.5", disabled && "cursor-not-allowed opacity-50")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn("relative h-5 w-9 rounded-full border transition", checked ? "border-accent bg-accent" : "border-line bg-card2")}
      >
        <span className={cn("absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow transition", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      {label && <span className="text-sm">{label}</span>}
    </label>
  );
}

export function Select({
  value,
  onChange,
  options,
  className,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
  disabled?: boolean;
}) {
  return (
    <div className={cn("relative", className)}>
      <select className="input appearance-none pr-8" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
    </div>
  );
}

export function TagInput({ value, onChange, placeholder, disabled }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string; disabled?: boolean }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const parts = draft
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .filter((s) => !value.includes(s));
    if (parts.length) onChange([...value, ...parts]);
    setDraft("");
  };
  return (
    <div className={cn("flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-line bg-deep/60 px-2 py-1.5", disabled && "opacity-60")}>
      {value.map((t) => (
        <span key={t} className="chip text-fg/90">
          {t}
          {!disabled && (
            <button onClick={() => onChange(value.filter((x) => x !== t))} className="text-subtle hover:text-danger">
              <X className="h-3 w-3" />
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <input
          className="min-w-[120px] flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-subtle"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add();
            } else if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1));
          }}
          onBlur={add}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Visual bits
// ---------------------------------------------------------------------------
export function ScoreRing({ score, size = 44, stroke = 4 }: { score: number; size?: number; stroke?: number }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const s = Math.max(0, Math.min(100, score || 0));
  const color = s >= 85 ? "rgb(var(--success))" : s >= 60 ? "rgb(var(--warn))" : "rgb(var(--danger))";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgb(var(--line))" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - s / 100)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-medium">{Math.round(s)}</span>
    </div>
  );
}

export function ProgressBar({ value, tone = "accent", className }: { value: number; tone?: "accent" | "success" | "danger" | "info"; className?: string }) {
  const bg = { accent: "bg-accent", success: "bg-success", danger: "bg-danger", info: "bg-info" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-line", className)}>
      <div className={cn("h-full rounded-full transition-all", bg)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Kv({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/60 py-2 text-sm last:border-0">
      <span className="text-muted">{k}</span>
      <span className="min-w-0 break-words text-right">{v}</span>
    </div>
  );
}

export function RoundIcon({ children, tone = "accent" }: { children: ReactNode; tone?: Tone }) {
  const cls = {
    neutral: "border-line bg-card2 text-muted",
    accent: "border-accent/25 bg-accent/10 text-accent shadow-[0_0_24px_-6px_rgb(var(--accent)/0.6)]",
    danger: "border-danger/25 bg-danger/10 text-danger shadow-[0_0_24px_-6px_rgb(var(--danger)/0.6)]",
    success: "border-success/25 bg-success/10 text-success shadow-[0_0_24px_-6px_rgb(var(--success)/0.6)]",
    info: "border-info/25 bg-info/10 text-info shadow-[0_0_24px_-6px_rgb(var(--info)/0.6)]",
    warn: "border-warn/25 bg-warn/10 text-warn shadow-[0_0_24px_-6px_rgb(var(--warn)/0.6)]",
  }[tone];
  return <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full border", cls)}>{children}</div>;
}
