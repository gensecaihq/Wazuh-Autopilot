import { useState } from "react";
import { Link } from "react-router-dom";
import { Cpu, Wrench } from "lucide-react";
import { useAgents } from "@/api/hooks";
import type { Agent } from "@/api/types";
import { Async, PageBody, PageHeader, ScoreRing, Segmented, StatusDot } from "@/components/ui";
import { AgentAvatar } from "@/components/icons";
import { fmtNum, relTime, titleCase } from "@/lib/format";
import { cn } from "@/lib/cn";

const CATS = ["all", "command", "detect", "investigate", "intel", "respond", "govern"] as const;
type Cat = (typeof CATS)[number];

export default function Agents() {
  const q = useAgents();
  const [cat, setCat] = useState<Cat>("all");
  return (
    <div>
      <PageHeader
        title="Agent Roster"
        subtitle="Specialist Strands agents that make up your SOC swarm"
        right={
          q.data && (
            <div className="flex items-center gap-4 text-sm text-muted">
              <span>
                <span className="text-fg">{q.data.filter((a) => a.enabled).length}</span> enabled
              </span>
              <span>
                <span className="text-accent">{q.data.filter((a) => a.status === "running").length}</span> running
              </span>
            </div>
          )
        }
      />
      <PageBody>
        <div className="scrollbar-thin overflow-x-auto">
          <Segmented size="sm" value={cat} onChange={setCat} options={CATS.map((c) => ({ value: c, label: c === "all" ? "All" : titleCase(c) }))} />
        </div>
        <Async q={q}>
          {(agents) => (
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {agents
                .filter((a) => cat === "all" || a.category === cat)
                .map((a) => (
                  <AgentCard key={a.id} a={a} />
                ))}
            </div>
          )}
        </Async>
      </PageBody>
    </div>
  );
}

export function AgentCard({ a }: { a: Agent }) {
  return (
    <Link to={`/agents/${a.id}`} className={cn("card group block p-4 transition hover:border-subtle/60", !a.enabled && "opacity-60")}>
      <div className="flex items-start gap-3">
        <AgentAvatar icon={a.icon} color={a.avatar_color} running={a.status === "running"} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-[15px]">{a.name}</span>
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted">
            <span className="font-medium" style={{ color: a.avatar_color }}>
              {a.codename}
            </span>
            <span>·</span>
            <span className="uppercase">{a.tier}</span>
            <span>·</span>
            <span className="flex items-center gap-1.5">
              <StatusDot value={a.enabled ? a.status : "disabled"} pulse={a.status === "running"} />
              {a.enabled ? a.status : "disabled"}
            </span>
          </div>
        </div>
        <ScoreRing score={a.health.score} />
      </div>
      <p className="mt-3 line-clamp-2 text-sm text-muted">{a.description}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {a.skills.slice(0, 4).map((s) => (
          <span key={s.id} className="chip">
            {s.name}
          </span>
        ))}
        {a.skills.length > 4 && <span className="chip">+{a.skills.length - 4}</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {a.standards.slice(0, 3).map((s) => (
          <span key={s.id} className="inline-flex items-center rounded-md border border-info/25 bg-info/5 px-1.5 py-0.5 text-[10.5px] text-info">
            {s.name}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-line/70 pt-3 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5" />
          <span className="max-w-[160px] truncate">{a.model.model_id}</span>
          {a.model.inherited && <span className="text-subtle">(default)</span>}
        </span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <Wrench className="h-3.5 w-3.5" />
            {a.tools_count}
          </span>
          <span>{fmtNum(a.health.runs_24h)} runs/24h</span>
          <span className="hidden sm:inline">{relTime(a.health.last_run_at)}</span>
        </span>
      </div>
    </Link>
  );
}
