import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleX, FlaskConical, Play } from "lucide-react";
import { useAgents, useEvalRuns, useEvalSuite, useEvalSuites, useRunEval } from "@/api/hooks";
import type { EvalRun } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Async, Card, CardHeader, EmptyState, PageBody, PageHeader, ProgressBar, Spinner, StatusBadge } from "@/components/ui";
import { SeriesChart, useColors } from "@/components/charts";
import { AgentAvatar } from "@/components/icons";
import { fmtPct, relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/cn";

export default function Evals() {
  const suites = useEvalSuites();
  const agents = useAgents();
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => {
    if (!sel && suites.data?.length) setSel(suites.data[0].id);
  }, [suites.data, sel]);
  const byId = new Map((agents.data ?? []).map((a) => [a.id, a]));

  return (
    <div>
      <PageHeader title="Evals" subtitle="Validate agents before you ship changes, using strands-agents-evals (tool selection, output checks, LLM-judged goal success)" />
      <PageBody>
        <Async q={suites} isEmpty={(d) => !d.length} empty={<Card><EmptyState icon={<FlaskConical className="h-5 w-5" />} title="No eval suites" /></Card>}>
          {(list) => (
            <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
              <div className="space-y-2">
                {list.map((s) => {
                  const a = byId.get(s.agent_id);
                  return (
                    <button
                      key={s.id}
                      onClick={() => setSel(s.id)}
                      className={cn("card flex w-full items-center gap-3 p-4 text-left transition", sel === s.id ? "border-accent/50 ring-1 ring-accent/20" : "hover:border-subtle/60")}
                    >
                      {a && <AgentAvatar icon={a.icon} color={a.avatar_color} size="sm" />}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{s.name}</div>
                        <div className="text-[11px] text-muted">
                          {s.cases} cases · {relTime(s.last_run_at)}
                        </div>
                      </div>
                      <ScorePill score={s.last_score} />
                    </button>
                  );
                })}
              </div>
              {sel && <SuiteDetail id={sel} />}
            </div>
          )}
        </Async>
      </PageBody>
    </div>
  );
}

function ScorePill({ score }: { score: number | null }) {
  if (score === null || score === undefined) return <span className="text-xs text-subtle">—</span>;
  const tone = score >= 0.85 ? "text-success border-success/30 bg-success/10" : score >= 0.6 ? "text-warn border-warn/30 bg-warn/10" : "text-danger border-danger/30 bg-danger/10";
  return <span className={cn("rounded-md border px-2 py-0.5 text-xs", tone)}>{fmtPct(score, 0, true)}</span>;
}

function SuiteDetail({ id }: { id: string }) {
  const suite = useEvalSuite(id);
  const runs = useEvalRuns(id);
  const run = useRunEval();
  const { can } = useAuth();
  const toast = useToast();
  const col = useColors();
  const list = useMemo(() => [...(runs.data?.items ?? [])].sort((a, b) => b.started_at.localeCompare(a.started_at)), [runs.data]);
  const latest = list[0];
  const trend = [...list]
    .reverse()
    .filter((r) => r.overall_score !== null)
    .map((r) => ({ ts: r.started_at, value: Math.round((r.overall_score ?? 0) * 100) }));

  return (
    <div className="min-w-0 space-y-4">
      <Card>
        <CardHeader
          title={suite.data?.name ?? "Suite"}
          subtitle={suite.data ? `Agent ${suite.data.agent_id} · evaluators: ${suite.data.evaluators.join(", ")}` : undefined}
          right={
            can("evals:run") && (
              <button
                className="btn-primary"
                disabled={run.isPending || latest?.status === "running"}
                onClick={() => run.mutate(id, { onSuccess: () => toast.success("Eval started"), onError: (e) => toast.error("Couldn't start eval", errorMessage(e)) })}
              >
                {run.isPending || latest?.status === "running" ? <Spinner className="text-black" /> : <Play className="h-4 w-4" />} Run suite
              </button>
            )
          }
        />
        <div className="grid gap-4 p-5 md:grid-cols-[1fr_1.4fr]">
          <div className="space-y-3">
            <div className="text-xs text-muted">Latest score</div>
            <div className="text-4xl font-light">{latest?.overall_score !== null && latest?.overall_score !== undefined ? fmtPct(latest.overall_score, 0, true) : "—"}</div>
            <div className="flex items-center gap-2 text-xs text-muted">
              {latest && <StatusBadge value={latest.status} />}
              {latest?.pass_rate !== null && latest?.pass_rate !== undefined && <span>{fmtPct(latest.pass_rate, 0, true)} of cases passed</span>}
            </div>
            <ProgressBar value={(latest?.overall_score ?? 0) * 100} tone={(latest?.overall_score ?? 0) >= 0.85 ? "success" : "accent"} />
          </div>
          <div>
            <div className="mb-1 text-xs text-muted">Score trend</div>
            {trend.length > 1 ? <SeriesChart series={[{ key: "s", label: "Score %", color: col.accent, points: trend }]} height={140} /> : <p className="py-10 text-center text-xs text-subtle">Run the suite a few times to see a trend.</p>}
          </div>
        </div>
      </Card>
      {latest && <Results run={latest} />}
      {suite.data && (
        <Card>
          <CardHeader title="Test cases" subtitle={`${suite.data.cases.length} cases`} />
          <div className="px-5 pb-4 pt-2">
            {suite.data.cases.map((c) => (
              <div key={c.name} className="border-b border-line/60 py-3 last:border-0">
                <div className="text-sm">{c.name}</div>
                <div className="mt-0.5 text-xs text-muted">{c.input}</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {c.expected_tools.map((t) => (
                    <span key={t} className="chip font-mono">
                      calls {t}
                    </span>
                  ))}
                  {c.expected_contains.map((t) => (
                    <span key={t} className="chip">
                      mentions “{t}”
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function Results({ run }: { run: EvalRun }) {
  const evaluators = Array.from(new Set(run.results.flatMap((r) => Object.keys(r.evaluator_scores))));
  return (
    <Card>
      <CardHeader title="Latest results" subtitle={`Started ${relTime(run.started_at)}`} />
      <div className="scrollbar-thin overflow-x-auto p-2">
        {!run.results.length && <p className="p-6 text-center text-sm text-muted">{run.status === "running" ? "Running…" : "No results."}</p>}
        {run.results.length > 0 && (
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-line">
                <th className="th">Case</th>
                <th className="th">Result</th>
                {evaluators.map((e) => (
                  <th key={e} className="th">
                    {e}
                  </th>
                ))}
                <th className="th">Reason</th>
              </tr>
            </thead>
            <tbody>
              {run.results.map((r) => (
                <tr key={r.case} className="border-b border-line/60 align-top last:border-0">
                  <td className="td">{r.case}</td>
                  <td className="td">
                    {r.passed ? <CheckCircle2 className="h-4 w-4 text-success" /> : <CircleX className="h-4 w-4 text-danger" />}
                  </td>
                  {evaluators.map((e) => (
                    <td key={e} className="td">
                      {r.evaluator_scores[e] !== undefined ? fmtPct(r.evaluator_scores[e], 0, true) : "—"}
                    </td>
                  ))}
                  <td className="td max-w-[360px] text-xs text-muted">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}
