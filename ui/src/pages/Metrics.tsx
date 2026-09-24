import { useState } from "react";
import { useAgents, useTimeseries } from "@/api/hooks";
import type { MetricName } from "@/api/types";
import { Card, CardHeader, ErrorState, PageBody, PageHeader, Segmented, Select, Skeleton } from "@/components/ui";
import { SeriesChart, useColors } from "@/components/charts";
import { fmtMs, fmtNum, fmtUsd } from "@/lib/format";

const METRICS: { id: MetricName; label: string; fmt: (v: number) => string; color: "accent" | "info" | "success" | "danger" | "warn" }[] = [
  { id: "runs", label: "Runs", fmt: (v) => fmtNum(v), color: "accent" },
  { id: "tokens", label: "Tokens", fmt: (v) => fmtNum(v), color: "info" },
  { id: "latency", label: "Avg latency", fmt: (v) => fmtMs(v), color: "warn" },
  { id: "errors", label: "Errors", fmt: (v) => fmtNum(v), color: "danger" },
  { id: "cost", label: "Model cost", fmt: (v) => fmtUsd(v), color: "success" },
  { id: "tool_calls", label: "Tool calls", fmt: (v) => fmtNum(v), color: "accent" },
];

const PALETTE = ["#ff8127", "#4f6bff", "#22c55e", "#ef4444", "#eab308", "#a855f7", "#14b8a6", "#ec4899", "#f97316", "#38bdf8", "#84cc16", "#f43f5e"];

export default function Metrics() {
  const [range, setRange] = useState<"24h" | "7d">("24h");
  const [agent, setAgent] = useState("");
  const agents = useAgents();
  return (
    <div>
      <PageHeader
        title="Metrics"
        subtitle="Swarm throughput, latency, errors and spend. Also exported at /metrics for Prometheus."
        right={
          <>
            <Select className="w-48" value={agent} onChange={setAgent} options={[{ value: "", label: "All agents" }, ...(agents.data ?? []).map((a) => ({ value: a.id, label: a.codename }))]} />
            <Segmented value={range} onChange={setRange} options={[{ value: "24h", label: "24h" }, { value: "7d", label: "7d" }]} />
          </>
        }
      />
      <PageBody>
        <div className="grid gap-4 xl:grid-cols-2">
          {METRICS.map((m) => (
            <MetricCard key={m.id} metric={m} range={range} agent={agent} />
          ))}
        </div>
        <BreakdownCard range={range} />
      </PageBody>
    </div>
  );
}

function MetricCard({ metric, range, agent }: { metric: (typeof METRICS)[number]; range: string; agent: string }) {
  const q = useTimeseries(metric.id, range, agent || undefined);
  const col = useColors();
  const total = (q.data?.points ?? []).reduce((s, p) => s + p.value, 0);
  const avg = q.data?.points.length ? total / q.data.points.length : 0;
  const headline = metric.id === "latency" ? metric.fmt(avg) : metric.fmt(total);
  return (
    <Card glow>
      <CardHeader title={metric.label} right={<span className="text-lg">{q.data ? headline : "—"}</span>} />
      <div className="p-3">
        {q.isLoading ? <Skeleton className="h-[200px]" /> : q.error ? <ErrorState error={q.error} /> : <SeriesChart series={[{ key: metric.id, label: metric.label, color: col[metric.color], points: q.data?.points ?? [] }]} valueFormatter={metric.fmt} height={200} />}
      </div>
    </Card>
  );
}

function BreakdownCard({ range }: { range: string }) {
  const [metric, setMetric] = useState<MetricName>("tokens");
  const q = useTimeseries(metric, range);
  const m = METRICS.find((x) => x.id === metric)!;
  const series = (q.data?.by_agent ?? []).map((b, i) => ({ key: b.agent_id.replace(/[^a-z0-9]/gi, "_"), label: b.agent_id, color: PALETTE[i % PALETTE.length], points: b.points }));
  return (
    <Card>
      <CardHeader
        title="By agent"
        subtitle="Which agents drive volume and cost"
        right={<Select className="w-40" value={metric} onChange={(v) => setMetric(v as MetricName)} options={METRICS.map((x) => ({ value: x.id, label: x.label }))} />}
      />
      <div className="p-3">
        {q.isLoading ? <Skeleton className="h-[280px]" /> : series.length ? <SeriesChart series={series} valueFormatter={m.fmt} height={280} area={false} /> : <p className="py-16 text-center text-sm text-muted">No per-agent data yet.</p>}
        <div className="flex flex-wrap gap-3 px-3 pb-2 text-xs text-muted">
          {series.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
