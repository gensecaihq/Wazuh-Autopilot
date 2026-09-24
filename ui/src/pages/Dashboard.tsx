import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowDown, ArrowRight, ArrowUp, Bot, ClipboardCheck, Clock, ShieldCheck, Siren, Radio, Activity } from "lucide-react";
import { useDashboard } from "@/api/hooks";
import type { DashboardSummary } from "@/api/types";
import { Card, CardHeader, DeltaChip, EmptyState, ErrorState, PageHeader, RoundIcon, Segmented, Skeleton } from "@/components/ui";
import { Donut, Legend, TrafficChart, WorldMap, useColors } from "@/components/charts";
import { fmtNum, fmtPct, fmtUsd, relTime } from "@/lib/format";
import { useEvents } from "@/lib/events";
import { describeEvent } from "@/components/Layout";
import { cn } from "@/lib/cn";

type Range = "24h" | "7d" | "30d";

export default function Dashboard() {
  const [range, setRange] = useState<Range>("24h");
  const q = useDashboard(range);
  const d = q.data;

  return (
    <div>
      <PageHeader
        title="Command Center"
        subtitle="Wazuh detections, agent activity and containment across your estate"
        right={<Segmented value={range} onChange={setRange} options={[{ value: "24h", label: "Day" }, { value: "7d", label: "Weekly" }, { value: "30d", label: "Monthly" }]} />}
      />
      {q.error ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : (
        <div className="space-y-4 p-4 md:p-6">
          <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
            <TrafficCard d={d} range={range} />
            <SummaryCard d={d} />
          </div>
          <SwarmStrip d={d} />
          <div className="grid gap-4 xl:grid-cols-2">
            <SourcesCard d={d} />
            <TargetsCard d={d} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <SeverityCard d={d} />
            <MitreCard d={d} />
            <ActivityFeed />
          </div>
        </div>
      )}
    </div>
  );
}

function TrafficCard({ d, range }: { d?: DashboardSummary; range: Range }) {
  const col = useColors();
  return (
    <Card glow className="overflow-hidden">
      <CardHeader
        title="Detections and response"
        right={<span className="text-xs text-muted">{range === "24h" ? "Hourly" : "Daily"} buckets</span>}
      />
      <div className="px-5 pt-2">
        <Legend
          items={[
            { label: "Alerts", color: col.accent },
            { label: "Incidents", color: col.danger },
            { label: "Actions", color: col.info },
            { label: "Contained", color: col.success },
          ]}
        />
      </div>
      <div className="px-2 pb-3 pt-2">{d ? <TrafficChart data={d.traffic} range={range} /> : <Skeleton className="mx-3 h-[290px]" />}</div>
    </Card>
  );
}

function SummaryCard({ d }: { d?: DashboardSummary }) {
  const rows = d
    ? [
        { icon: <Siren className="h-4 w-4" />, tone: "danger" as const, value: fmtNum(d.kpis.incidents.value), label: "Incidents", delta: d.kpis.incidents.delta_pct, goodDown: true, to: "/cases" },
        { icon: <ShieldCheck className="h-4 w-4" />, tone: "success" as const, value: fmtNum(d.kpis.auto_contained.value), label: "Threats contained", delta: d.kpis.auto_contained.delta_pct, goodDown: false, to: "/approvals" },
        { icon: <Radio className="h-4 w-4" />, tone: "accent" as const, value: fmtNum(d.kpis.alerts.value), label: "Alerts", delta: d.kpis.alerts.delta_pct, goodDown: true, to: "/alerts" },
        { icon: <Clock className="h-4 w-4" />, tone: "info" as const, value: `${fmtNum(d.kpis.mttr_minutes.value)}m`, label: "Mean time to respond", delta: d.kpis.mttr_minutes.delta_pct, goodDown: true, to: "/metrics" },
        { icon: <ClipboardCheck className="h-4 w-4" />, tone: "warn" as const, value: fmtNum(d.kpis.pending_approvals.value), label: "Pending approvals", delta: null, goodDown: true, to: "/approvals" },
      ]
    : [];
  return (
    <Card className="bg-gradient-to-b from-card to-bg">
      <CardHeader title="Summary for the period" />
      <div className="px-5 pb-3 pt-2">
        {!d &&
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 border-b border-line/70 py-3.5 last:border-0">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-28" />
              </div>
            </div>
          ))}
        {rows.map((r) => (
          <Link key={r.label} to={r.to} className="group flex items-center gap-3.5 border-b border-line/70 py-3 last:border-0">
            <RoundIcon tone={r.tone}>{r.icon}</RoundIcon>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-lg leading-tight">{r.value}</span>
                {r.delta !== null && <DeltaChip value={r.delta} goodWhenDown={r.goodDown} />}
              </div>
              <div className="text-sm text-muted">{r.label}</div>
            </div>
            <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-fg" />
          </Link>
        ))}
      </div>
    </Card>
  );
}

function SwarmStrip({ d }: { d?: DashboardSummary }) {
  const s = d?.swarm;
  const items = [
    { label: "Agents active", value: s ? `${s.agents_active}/${s.agents_total}` : "—", icon: Bot },
    { label: "Runs (24h)", value: s ? fmtNum(s.runs_24h) : "—", icon: Activity },
    { label: "Run success", value: s ? fmtPct(s.success_rate, 1, true) : "—", icon: ShieldCheck },
    { label: "Tokens (24h)", value: s ? fmtNum(s.tokens_24h) : "—", icon: Radio },
    { label: "Model cost (24h)", value: s ? fmtUsd(s.cost_24h_usd) : "—", icon: Clock },
  ];
  return (
    <Card className="grid grid-cols-2 divide-line sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
      {items.map((i) => (
        <Link to="/health" key={i.label} className="flex items-center gap-3 px-5 py-3.5 hover:bg-card2/40">
          <i.icon className="h-4 w-4 text-accent" />
          <div>
            <div className="text-[15px]">{i.value}</div>
            <div className="text-xs text-muted">{i.label}</div>
          </div>
        </Link>
      ))}
    </Card>
  );
}

function SourcesCard({ d }: { d?: DashboardSummary }) {
  const [tab, setTab] = useState<"map" | "list">("map");
  const pts = d?.attack_sources ?? [];
  return (
    <Card>
      <CardHeader
        title="Attack sources"
        right={<Segmented size="sm" value={tab} onChange={setTab} options={[{ value: "map", label: "Locations" }, { value: "list", label: "Ranking" }]} />}
      />
      <div className="p-3">
        {!d ? (
          <Skeleton className="h-[320px]" />
        ) : tab === "map" ? (
          pts.length ? (
            <WorldMap points={pts.map((p) => ({ key: p.country, label: p.country_name, lat: p.lat, lon: p.lon, value: p.count, pct: p.pct, flag: p.country }))} height={330} />
          ) : (
            <EmptyState title="No external sources" body="No alerts with a geolocated source IP in this period." />
          )
        ) : (
          <div className="space-y-2.5 px-2 py-1">
            {pts.slice(0, 10).map((p) => (
              <div key={p.country}>
                <div className="flex justify-between text-sm">
                  <span>{p.country_name}</span>
                  <span className="text-muted">
                    {fmtNum(p.count)} · {p.pct.toFixed(1)}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-line">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, (p.count / Math.max(1, pts[0]?.count ?? 1)) * 100)}%` }} />
                </div>
              </div>
            ))}
            {!pts.length && <EmptyState title="No external sources" />}
          </div>
        )}
      </div>
    </Card>
  );
}

function TargetsCard({ d }: { d?: DashboardSummary }) {
  const rows = d?.top_targets ?? [];
  const max = Math.max(1, ...rows.map((r) => r.alerts));
  return (
    <Card>
      <CardHeader title="Most targeted endpoints" subtitle="Wazuh agents ranked by alert volume" />
      <div className="px-5 pb-4 pt-3">
        {!d ? (
          <Skeleton className="h-[320px]" />
        ) : !rows.length ? (
          <EmptyState title="No targets yet" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted">
                <th className="pb-2 text-left font-normal">Endpoint</th>
                <th className="pb-2 text-right font-normal">Incidents</th>
                <th className="pb-2 text-right font-normal">Alerts</th>
                <th className="pb-2 text-right font-normal">Trend</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 10).map((r) => (
                <tr key={r.agent_id} className="border-t border-line/50">
                  <td className="py-1.5">
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 rounded bg-card2" style={{ width: `${Math.max(18, (r.alerts / max) * 100)}%` }} />
                      <div className="relative truncate px-1.5 py-1">
                        {r.agent_name} <span className="text-xs text-subtle">{r.ip}</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-1.5 text-right">
                    {r.incidents > 0 ? (
                      <span className="inline-flex min-w-[26px] justify-center rounded-md border border-danger/30 bg-danger/10 px-1.5 text-xs text-danger">{r.incidents}</span>
                    ) : (
                      <span className="text-subtle">--</span>
                    )}
                  </td>
                  <td className="py-1.5 text-right">{fmtNum(r.alerts)}</td>
                  <td className={cn("py-1.5 text-right", r.trend_pct > 0 ? "text-danger" : "text-success")}>
                    <span className="inline-flex items-center gap-0.5">
                      {Math.abs(r.trend_pct).toFixed(1)}%{r.trend_pct > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}

function SeverityCard({ d }: { d?: DashboardSummary }) {
  const col = useColors();
  const colors: Record<string, string> = { critical: col.danger, high: col.accent, medium: col.warn, low: col.info, informational: col.subtle };
  const data = (d?.severity_breakdown ?? []).map((s) => ({ name: s.severity, value: s.count, color: colors[s.severity] ?? col.subtle }));
  return (
    <Card>
      <CardHeader title="Alert severity" />
      <div className="grid grid-cols-[1fr_1fr] items-center gap-2 p-4">
        {d ? <Donut data={data} centerLabel="alerts" /> : <Skeleton className="h-[180px]" />}
        <div className="space-y-2">
          {data.map((s) => (
            <div key={s.name} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 capitalize text-muted">
                <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                {s.name === "informational" ? "info" : s.name}
              </span>
              <span>{fmtNum(s.value)}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function MitreCard({ d }: { d?: DashboardSummary }) {
  const rows = d?.mitre_top ?? [];
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <Card>
      <CardHeader title="Top MITRE ATT&CK techniques" />
      <div className="space-y-3 p-5 pt-4">
        {!d && <Skeleton className="h-[170px]" />}
        {d && !rows.length && <EmptyState title="No techniques mapped" />}
        {rows.slice(0, 6).map((r) => (
          <div key={r.technique_id}>
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate">
                <span className="mr-1.5 font-mono text-xs text-accent">{r.technique_id}</span>
                {r.name}
              </span>
              <span className="text-muted">{fmtNum(r.count)}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full bg-accent/80" style={{ width: `${(r.count / max) * 100}%` }} />
              </div>
              <span className="w-28 truncate text-right text-[10.5px] text-subtle">{r.tactic}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ActivityFeed() {
  const { events, connected } = useEvents();
  const navigate = useNavigate();
  const items = events.filter((e) => e.type !== "run.step").slice(0, 12);
  return (
    <Card className="lg:col-span-2 xl:col-span-1">
      <CardHeader
        title="Live swarm activity"
        right={
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <span className={cn("h-1.5 w-1.5 rounded-full", connected ? "animate-pulse bg-success" : "bg-subtle")} />
            {connected ? "streaming" : "offline"}
          </span>
        }
      />
      <div className="scrollbar-thin max-h-[260px] overflow-y-auto px-5 pb-4 pt-2">
        {!items.length && <p className="py-10 text-center text-sm text-muted">Waiting for agent activity…</p>}
        {items.map((e, i) => {
          const d = e.data;
          const target =
            e.type.startsWith("run.") && typeof d.run_id === "string"
              ? `/runs/${d.run_id}`
              : e.type.startsWith("case.") && typeof d.id === "string"
                ? `/cases/${d.id}`
                : e.type.startsWith("action.")
                  ? "/approvals"
                  : null;
          return (
            <button
              key={i}
              onClick={() => target && navigate(target)}
              className="flex w-full items-start gap-3 border-b border-line/50 py-2 text-left last:border-0"
            >
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span className="min-w-0 flex-1 text-sm">{describeEvent(e.type, d)}</span>
              <span className="shrink-0 text-[11px] text-subtle">{relTime(new Date(e.at).toISOString())}</span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
