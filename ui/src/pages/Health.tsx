import { useNavigate } from "react-router-dom";
import { Cpu, Database, Plug, Server, Timer, Webhook, Activity } from "lucide-react";
import { useAgents, useSystemHealth } from "@/api/hooks";
import type { Agent } from "@/api/types";
import { Async, Card, CardHeader, DataTable, PageBody, PageHeader, ScoreRing, StatusBadge, StatusDot, type Column } from "@/components/ui";
import { AgentAvatar } from "@/components/icons";
import { fmtMs, fmtNum, fmtPct, fmtUsd, relTime } from "@/lib/format";
import { cn } from "@/lib/cn";

const ICON: Record<string, typeof Server> = { api: Server, database: Database, wazuh_mcp: Plug, model: Cpu, scheduler: Timer, ingestion: Webhook };

export default function Health() {
  const sys = useSystemHealth();
  const agents = useAgents();
  const navigate = useNavigate();

  const cols: Column<Agent>[] = [
    {
      key: "agent",
      header: "Agent",
      cell: (a) => (
        <div className="flex items-center gap-2.5">
          <AgentAvatar icon={a.icon} color={a.avatar_color} size="sm" running={a.status === "running"} />
          <div>
            <div className="whitespace-nowrap">{a.codename}</div>
            <div className="text-[11px] text-subtle">{a.name}</div>
          </div>
        </div>
      ),
      sort: (a) => a.codename,
    },
    { key: "score", header: "Health", cell: (a) => <ScoreRing score={a.health.score} size={34} stroke={3} />, sort: (a) => a.health.score },
    { key: "status", header: "Status", cell: (a) => <StatusBadge value={a.enabled ? a.health.status : "disabled"} />, sort: (a) => a.health.status },
    { key: "runs", header: "Runs 24h", cell: (a) => fmtNum(a.health.runs_24h), sort: (a) => a.health.runs_24h },
    { key: "err", header: "Error rate", cell: (a) => <span className={cn(a.health.error_rate > 0.1 && "text-danger")}>{fmtPct(a.health.error_rate, 1, true)}</span>, sort: (a) => a.health.error_rate },
    { key: "avg", header: "Avg latency", cell: (a) => fmtMs(a.health.avg_latency_ms), sort: (a) => a.health.avg_latency_ms },
    { key: "p95", header: "p95", cell: (a) => fmtMs(a.health.p95_latency_ms), sort: (a) => a.health.p95_latency_ms },
    { key: "tok", header: "Tokens 24h", cell: (a) => fmtNum(a.health.tokens_24h), sort: (a) => a.health.tokens_24h },
    { key: "cost", header: "Cost 24h", cell: (a) => fmtUsd(a.health.cost_24h_usd), sort: (a) => a.health.cost_24h_usd },
    { key: "last", header: "Last run", cell: (a) => <span className="whitespace-nowrap text-muted">{relTime(a.health.last_run_at)}</span>, sort: (a) => a.health.last_run_at ?? "" },
    {
      key: "lasterr",
      header: "Last error",
      cell: (a) => (a.health.last_error ? <span className="line-clamp-1 max-w-[220px] text-xs text-danger" title={a.health.last_error}>{a.health.last_error}</span> : <span className="text-subtle">—</span>),
    },
  ];

  return (
    <div>
      <PageHeader title="Agent Health" subtitle="Platform components and per-agent reliability, latency and spend" />
      <PageBody>
        <Async q={sys}>
          {(s) => (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
                {s.components.map((c) => {
                  const I = ICON[c.id] ?? Activity;
                  return (
                    <Card key={c.id} className="p-4">
                      <div className="flex items-center justify-between">
                        <I className="h-4 w-4 text-muted" />
                        <StatusDot value={c.status} pulse={c.status === "down"} />
                      </div>
                      <div className="mt-3 text-sm">{c.name}</div>
                      <div className="mt-0.5 flex items-center gap-2 text-xs">
                        <span className={cn(c.status === "healthy" ? "text-success" : c.status === "degraded" ? "text-warn" : c.status === "down" ? "text-danger" : "text-muted")}>{c.status}</span>
                        {c.latency_ms !== null && <span className="text-subtle">{fmtMs(c.latency_ms)}</span>}
                      </div>
                      <div className="mt-2 line-clamp-2 text-[11px] text-subtle" title={c.detail}>
                        {c.detail}
                      </div>
                    </Card>
                  );
                })}
              </div>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[
                  { k: "Agents", v: s.swarm.agents_total },
                  { k: "Healthy agents", v: s.swarm.agents_healthy },
                  { k: "Runs in progress", v: s.swarm.runs_running },
                  { k: "Queue depth", v: s.swarm.queue_depth },
                ].map((x) => (
                  <Card key={x.k} className="p-4">
                    <div className="text-xs text-muted">{x.k}</div>
                    <div className="mt-1 text-2xl font-light">{x.v}</div>
                  </Card>
                ))}
              </div>
            </>
          )}
        </Async>
        <Card>
          <CardHeader title="Per-agent health" subtitle="Score blends error rate, latency and recency" />
          <div className="pt-2">
            <Async q={agents}>{(list) => <DataTable rows={list} columns={cols} rowKey={(a) => a.id} onRowClick={(a) => navigate(`/agents/${a.id}`)} initialSort={{ key: "score", dir: "asc" }} />}</Async>
          </div>
        </Card>
      </PageBody>
    </div>
  );
}
