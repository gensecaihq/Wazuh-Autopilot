export function fmtNum(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${trim((n / 1e9).toFixed(digits))}B`;
  if (abs >= 1e6) return `${trim((n / 1e6).toFixed(digits + 1))}M`;
  if (abs >= 1e3) return `${trim((n / 1e3).toFixed(digits))}K`;
  if (Number.isInteger(n)) return String(n);
  return trim(n.toFixed(digits));
}

function trim(s: string): string {
  return s.includes(".") ? s.replace(/\.?0+$/, "") : s;
}

export function fmtPct(v: number | null | undefined, digits = 1, isRatio = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const x = isRatio ? v * 100 : v;
  return `${trim(x.toFixed(digits))}%`;
}

export function fmtUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v < 0.01 && v > 0) return "<$0.01";
  return `$${v >= 100 ? fmtNum(v) : v.toFixed(2)}`;
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${trim((ms / 1000).toFixed(1))}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const diff = (Date.now() - t) / 1000;
  const fut = diff < 0;
  const d = Math.abs(diff);
  let out: string;
  if (d < 45) out = "just now";
  else if (d < 3600) out = `${Math.round(d / 60)}m`;
  else if (d < 86400) out = `${Math.round(d / 3600)}h`;
  else if (d < 86400 * 30) out = `${Math.round(d / 86400)}d`;
  else return new Date(iso).toLocaleDateString();
  if (out === "just now") return out;
  return fut ? `in ${out}` : `${out} ago`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function titleCase(s: string): string {
  return s.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}
