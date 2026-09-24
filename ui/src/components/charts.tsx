import { useMemo, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { geoEqualEarth, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { FeatureCollection, Geometry } from "geojson";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "@/assets/countries-110m.json";
import { fmtNum } from "@/lib/format";
import { useTheme } from "@/lib/theme";

// Resolved at render time so charts follow the active theme.
function useColors() {
  const { theme } = useTheme();
  return useMemo(() => {
    const css = getComputedStyle(document.documentElement);
    const c = (n: string, a = 1) => `rgb(${css.getPropertyValue(`--${n}`).trim()} / ${a})`;
    return {
      accent: c("accent"),
      accentSoft: c("accent", 0.35),
      danger: c("danger"),
      success: c("success"),
      info: c("info"),
      warn: c("warn"),
      muted: c("muted"),
      subtle: c("subtle"),
      line: c("line"),
      card: c("card2"),
      fg: c("fg"),
      c,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);
}
export { useColors };

// ---------------------------------------------------------------------------
// Tooltip card like the design
// ---------------------------------------------------------------------------
interface TipProps {
  active?: boolean;
  label?: string | number;
  payload?: { name?: string; value?: number | string; color?: string; dataKey?: string | number }[];
  labelFormatter?: (l: string | number) => string;
  valueFormatter?: (v: number) => string;
}

export function TooltipCard({ active, payload, label, labelFormatter, valueFormatter }: TipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-[150px] rounded-lg border border-line bg-card2/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1.5 flex items-center gap-1.5 text-fg">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        {label !== undefined ? (labelFormatter ? labelFormatter(label) : String(label)) : ""}
      </div>
      {payload.map((p) => (
        <div key={String(p.dataKey ?? p.name)} className="flex items-center justify-between gap-4 py-0.5">
          <span className="text-muted">{p.name}</span>
          <span className="text-fg">{typeof p.value === "number" ? (valueFormatter ? valueFormatter(p.value) : fmtNum(p.value)) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Traffic chart: orange gradient area + faint histogram + extra lines
// ---------------------------------------------------------------------------
export function TrafficChart({
  data,
  range,
  height = 290,
}: {
  data: { ts: string; alerts: number; incidents: number; actions: number; blocked: number }[];
  range: string;
  height?: number;
}) {
  const col = useColors();
  const fmtTick = (ts: string) => {
    const d = new Date(ts);
    return range === "24h" ? d.toLocaleTimeString(undefined, { hour: "2-digit" }) : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };
  const fmtLabel = (ts: string | number) => {
    const d = new Date(ts);
    return range === "24h"
      ? d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
      : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  };
  const maxAlerts = Math.max(1, ...data.map((d) => d.alerts));
  const maxSecondary = Math.max(1, ...data.map((d) => Math.max(d.incidents, d.actions, d.blocked)));
  const withBars = data.map((d) => ({ ...d, histo: d.alerts }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={withBars} margin={{ top: 10, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="gAlerts" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={col.accent} stopOpacity={0.32} />
            <stop offset="100%" stopColor={col.accent} stopOpacity={0} />
          </linearGradient>
          <pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.8" fill={col.c("muted", 0.18)} />
          </pattern>
        </defs>
        <CartesianGrid stroke="url(#dots)" vertical={false} horizontal={false} fill="url(#dots)" />
        <XAxis dataKey="ts" tickFormatter={fmtTick} tick={{ fill: col.subtle, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
        <YAxis yAxisId="a" tick={{ fill: col.subtle, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: number) => fmtNum(v)} width={44} />
        <YAxis yAxisId="h" hide domain={[0, maxAlerts * 4]} />
        <YAxis yAxisId="b" hide orientation="right" domain={[0, maxSecondary * 2.4]} />
        <Tooltip
          cursor={{ stroke: col.c("fg", 0.25), strokeDasharray: "3 3" }}
          content={<TooltipCard labelFormatter={fmtLabel} />}
        />
        <Bar yAxisId="h" dataKey="histo" name="volume" barSize={2} fill={col.c("muted", 0.28)} isAnimationActive={false} legendType="none" tooltipType="none" />
        <Area yAxisId="a" type="linear" dataKey="alerts" name="Alerts" stroke={col.accent} strokeWidth={1.6} fill="url(#gAlerts)" activeDot={{ r: 5, fill: col.accent, stroke: col.c("accent", 0.35), strokeWidth: 6 }} />
        <Line yAxisId="b" type="linear" dataKey="incidents" name="Incidents" stroke={col.danger} strokeOpacity={0.85} strokeWidth={1.2} dot={false} />
        <Line yAxisId="b" type="linear" dataKey="actions" name="Actions" stroke={col.info} strokeOpacity={0.85} strokeWidth={1.2} dot={false} />
        <Line yAxisId="b" type="linear" dataKey="blocked" name="Contained" stroke={col.success} strokeOpacity={0.85} strokeWidth={1.1} dot={false} strokeDasharray="4 3" />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-sm text-muted">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-2">
          <svg width="22" height="10">
            <line x1="0" y1="5" x2="22" y2="5" stroke={i.color} strokeWidth="1.6" />
            <circle cx="11" cy="5" r="3.2" fill="rgb(var(--card))" stroke={i.color} strokeWidth="1.6" />
          </svg>
          {i.label}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Simple time-series line (metrics pages)
// ---------------------------------------------------------------------------
export function SeriesChart({
  series,
  height = 220,
  valueFormatter,
  area = true,
}: {
  series: { key: string; label: string; color: string; points: { ts: string; value: number }[] }[];
  height?: number;
  valueFormatter?: (v: number) => string;
  area?: boolean;
}) {
  const col = useColors();
  const merged = useMemo(() => {
    const map = new Map<string, Record<string, number | string>>();
    for (const s of series)
      for (const p of s.points) {
        const row = map.get(p.ts) ?? { ts: p.ts };
        row[s.key] = p.value;
        map.set(p.ts, row);
      }
    return [...map.values()].sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
  }, [series]);
  const fmtTick = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: merged.length > 30 ? undefined : "2-digit" });
  };
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={merged} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.key} id={`g-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid stroke={col.c("line", 0.8)} vertical={false} />
        <XAxis dataKey="ts" tickFormatter={fmtTick} tick={{ fill: col.subtle, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} />
        <YAxis tick={{ fill: col.subtle, fontSize: 11 }} axisLine={false} tickLine={false} width={48} tickFormatter={(v: number) => (valueFormatter ? valueFormatter(v) : fmtNum(v))} />
        <Tooltip content={<TooltipCard labelFormatter={(l) => new Date(l).toLocaleString()} valueFormatter={valueFormatter} />} />
        {series.map((s) =>
          area ? (
            <Area key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={1.6} fill={`url(#g-${s.key})`} />
          ) : (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={1.6} dot={false} />
          ),
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function Sparkline({ values, color, height = 32 }: { values: number[]; color?: string; height?: number }) {
  const col = useColors();
  const data = values.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <Line type="monotone" dataKey="v" stroke={color ?? col.accent} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Donut
// ---------------------------------------------------------------------------
export function Donut({
  data,
  height = 180,
  centerLabel,
  centerValue,
}: {
  data: { name: string; value: number; color: string }[];
  height?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="relative" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={total ? data : [{ name: "none", value: 1, color: "rgb(var(--line))" }]} dataKey="value" innerRadius="68%" outerRadius="92%" paddingAngle={total ? 2 : 0} stroke="none">
            {(total ? data : [{ color: "rgb(var(--line))" }]).map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Pie>
          {total > 0 && <Tooltip content={<TooltipCard />} />}
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-xl">{centerValue ?? fmtNum(total)}</div>
        {centerLabel && <div className="text-[11px] text-muted">{centerLabel}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// World map with glowing dots
// ---------------------------------------------------------------------------
type WorldTopo = Topology<{ countries: GeometryCollection }>;
let LAND: FeatureCollection<Geometry> | null = null;
function land(): FeatureCollection<Geometry> {
  if (!LAND) {
    const topo = world as unknown as WorldTopo;
    LAND = feature(topo, topo.objects.countries) as unknown as FeatureCollection<Geometry>;
  }
  return LAND;
}

export interface MapPoint {
  key: string;
  label: string;
  lat: number;
  lon: number;
  value: number;
  pct?: number;
  flag?: string;
}

function flagEmoji(cc: string): string {
  if (!/^[A-Za-z]{2}$/.test(cc)) return "🌐";
  return String.fromCodePoint(...cc.toUpperCase().split("").map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

export function WorldMap({ points, height = 340 }: { points: MapPoint[]; height?: number }) {
  const W = 800;
  const H = 420;
  const [hover, setHover] = useState<MapPoint | null>(null);
  const { projection, paths } = useMemo(() => {
    const fc = land();
    const proj = geoEqualEarth().fitExtent(
      [
        [8, 8],
        [W - 8, H - 8],
      ],
      { type: "Sphere" },
    );
    const gp = geoPath(proj);
    return { projection: proj, paths: fc.features.filter((f) => (f.id as string) !== "010").map((f) => gp(f) ?? "") };
  }, []);
  const max = Math.max(1, ...points.map((p) => p.value));
  const top = hover ?? [...points].sort((a, b) => b.value - a.value)[0] ?? null;
  const topXY = top ? projection([top.lon, top.lat]) : null;

  return (
    <div className="relative w-full" style={{ height }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <pattern id="landDots" width="5" height="5" patternUnits="userSpaceOnUse">
            <circle cx="2.5" cy="2.5" r="1" fill="rgb(var(--muted) / 0.35)" />
          </pattern>
          <radialGradient id="dotGlow">
            <stop offset="0%" stopColor="rgb(var(--accent))" stopOpacity="0.9" />
            <stop offset="45%" stopColor="rgb(var(--accent))" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(var(--accent))" stopOpacity="0" />
          </radialGradient>
        </defs>
        <g>
          {paths.map((d, i) => (
            <path key={i} d={d} fill="rgb(var(--card2))" stroke="rgb(var(--line))" strokeWidth={0.5} />
          ))}
          {paths.map((d, i) => (
            <path key={`p${i}`} d={d} fill="url(#landDots)" />
          ))}
        </g>
        {points.map((p) => {
          const xy = projection([p.lon, p.lat]);
          if (!xy) return null;
          const r = 3 + (p.value / max) * 5;
          return (
            <g key={p.key} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} className="cursor-pointer">
              <circle cx={xy[0]} cy={xy[1]} r={r * 3.2} fill="url(#dotGlow)" />
              <circle cx={xy[0]} cy={xy[1]} r={r * 0.55} fill="rgb(var(--accent))" />
            </g>
          );
        })}
      </svg>
      {top && topXY && (
        <div
          className="pointer-events-none absolute w-[150px] rounded-lg border border-line bg-card2/90 p-2.5 text-xs shadow-xl backdrop-blur"
          style={{
            left: `clamp(0px, calc(${(topXY[0] / W) * 100}% - 75px), calc(100% - 150px))`,
            top: `clamp(0px, calc(${(topXY[1] / H) * 100}% - 86px), calc(100% - 80px))`,
          }}
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-fg">
              <span className="text-base leading-none">{flagEmoji(top.flag ?? top.key)}</span>
              <span className="max-w-[90px] truncate">{top.label}</span>
            </span>
            <span className="text-success">↗</span>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span>
              <span className="text-sm text-fg">{fmtNum(top.value)}</span> <span className="text-[10px] text-muted">attacks</span>
            </span>
            {top.pct !== undefined && <span className="text-fg">{top.pct.toFixed(0)}%</span>}
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line">
            <div className="h-full rounded-full bg-info" style={{ width: `${Math.min(100, (top.value / max) * 100)}%` }} />
          </div>
        </div>
      )}
    </div>
  );
}
