import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAgents, useRuns } from "@/api/hooks";
import { Async, Card, CardHeader, PageBody, PageHeader, StatusDot } from "@/components/ui";
import { SwarmGraph } from "@/components/Graph";
import { AgentAvatar } from "@/components/icons";
import { useEvents } from "@/lib/events";
import { describeEvent } from "@/components/Layout";
import { relTime, titleCase } from "@/lib/format";

export default function Swarm() {
  const agents = useAgents();
  const running = useRuns({ status: "running" });
  const { events } = useEvents();
  const [sel, setSel] = useState<string | null>(null);
  const handoffs = useMemo(() => events.filter((e) => e.type === "run.step" && (e.data.kind === "handoff" || e.data.to)).slice(0, 15), [events]);

  return (
    <div>
      <PageHeader title="Swarm Topology" subtitle="Who can hand work to whom. Running agents pulse; hover an agent to trace its handoffs." />
      <PageBody>
        <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
          <Card glow className="p-2">
            <Async q={agents}>{(list) => <SwarmGraph agents={list} highlight={sel} />}</Async>
          </Card>
          <div className="space-y-4">
            <Card>
              <CardHeader title="By function" />
              <div className="px-4 pb-4 pt-2">
                {Object.entries(
                  (agents.data ?? []).reduce<Record<string, typeof agents.data>>((acc, a) => {
                    (acc[a.category] ??= []).push(a);
                    return acc;
                  }, {}),
                ).map(([cat, list]) => (
                  <div key={cat} className="mb-3 last:mb-0">
                    <div className="mb-1 text-[11px] text-subtle">{titleCase(cat)}</div>
                    {list?.map((a) => (
                      <Link
                        key={a.id}
                        to={`/agents/${a.id}`}
                        onMouseEnter={() => setSel(a.id)}
                        onMouseLeave={() => setSel(null)}
                        className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-card2"
                      >
                        <AgentAvatar icon={a.icon} color={a.avatar_color} size="sm" running={a.status === "running"} />
                        <span className="min-w-0 flex-1 truncate text-sm">{a.codename}</span>
                        <StatusDot value={a.enabled ? a.status : "disabled"} pulse={a.status === "running"} />
                      </Link>
                    ))}
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <CardHeader title="Active runs" subtitle={`${running.data?.total ?? 0} running`} />
              <div className="px-4 pb-4 pt-2">
                {(running.data?.items ?? []).slice(0, 6).map((r) => (
                  <Link key={r.id} to={`/runs/${r.id}`} className="block rounded-lg px-2 py-1.5 hover:bg-card2">
                    <div className="text-sm">{r.workflow_name}</div>
                    <div className="text-[11px] text-muted">
                      {r.agents.join(" → ")} · {relTime(r.started_at)}
                    </div>
                  </Link>
                ))}
                {!running.data?.items.length && <p className="py-3 text-sm text-muted">Swarm is idle.</p>}
              </div>
            </Card>
            <Card>
              <CardHeader title="Recent handoffs" />
              <div className="px-4 pb-4 pt-2">
                {handoffs.map((e, i) => (
                  <div key={i} className="border-b border-line/50 py-1.5 text-xs last:border-0">
                    {typeof e.data.from === "string" && typeof e.data.to === "string" ? (
                      <>
                        <span className="text-fg">{e.data.from}</span> → <span className="text-accent">{e.data.to}</span>
                      </>
                    ) : (
                      describeEvent(e.type, e.data)
                    )}
                  </div>
                ))}
                {!handoffs.length && <p className="py-2 text-sm text-muted">No handoffs streamed yet.</p>}
              </div>
            </Card>
          </div>
        </div>
      </PageBody>
    </div>
  );
}
