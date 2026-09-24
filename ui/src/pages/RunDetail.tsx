import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, ChevronDown, ChevronRight, RotateCcw, Square } from "lucide-react";
import { useRun, useRunOp } from "@/api/hooks";
import type { Run, Span } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Card, CardHeader, ErrorState, JsonView, Kv, Markdown, SkeletonRows, StatusBadge, Tabs } from "@/components/ui";
import { fmtDateTime, fmtMs, fmtNum, fmtUsd, relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/cn";

const KIND_COLOR: Record<Span["kind"], string> = {
  run: "bg-subtle",
  agent: "bg-accent",
  model: "bg-info",
  tool: "bg-success",
  handoff: "bg-warn",
  guardrail: "bg-danger",
};
const KIND_TEXT: Record<Span["kind"], string> = {
  run: "text-muted",
  agent: "text-accent",
  model: "text-info",
  tool: "text-success",
  handoff: "text-warn",
  guardrail: "text-danger",
};

type Tab = "trace" | "output" | "input";

export default function RunDetail() {
  const { id = "" } = useParams();
  const [live, setLive] = useState(true);
  const q = useRun(id, live);
  useEffect(() => {
    if (q.data) setLive(q.data.status === "running" || q.data.status === "queued");
  }, [q.data]);
  const [tab, setTab] = useState<Tab>("trace");

  if (q.isLoading) return <SkeletonRows rows={10} />;
  if (q.error || !q.data) return <ErrorState error={q.error ?? "Not found"} onRetry={() => q.refetch()} />;
  const r = q.data;

  return (
    <div>
      <RunHeader r={r} />
      <div className="grid grid-cols-2 gap-3 px-4 pt-4 md:grid-cols-4 md:px-6 xl:grid-cols-7">
        {[
          { k: "Duration", v: fmtMs(r.duration_ms) },
          { k: "Agents", v: r.agents.length },
          { k: "Spans", v: r.spans.length },
          { k: "Tool calls", v: r.tool_calls },
          { k: "Tokens in / out", v: `${fmtNum(r.tokens_in)} / ${fmtNum(r.tokens_out)}` },
          { k: "Cost", v: fmtUsd(r.cost_usd) },
          { k: "Errors", v: r.errors },
        ].map((s) => (
          <Card key={s.k} className="p-3">
            <div className="text-[11px] text-muted">{s.k}</div>
            <div className={cn("mt-0.5 text-lg", s.k === "Errors" && r.errors > 0 && "text-danger")}>{s.v}</div>
          </Card>
        ))}
      </div>
      <div className="px-4 pt-2 md:px-6">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "trace", label: "Trace", count: r.spans.length },
            { value: "output", label: "Output" },
            { value: "input", label: "Input" },
          ]}
        />
      </div>
      <div className="p-4 md:p-6">
        {tab === "trace" && <Trace r={r} />}
        {tab === "output" && (
          <Card className="p-5">
            <Markdown>{r.output_md ?? (r.status === "running" ? "_Run in progress…_" : null)}</Markdown>
          </Card>
        )}
        {tab === "input" && <JsonView value={r.input} />}
      </div>
    </div>
  );
}

function RunHeader({ r }: { r: Run }) {
  const { can } = useAuth();
  const op = useRunOp();
  const toast = useToast();
  const navigate = useNavigate();
  return (
    <div className="border-b border-line px-4 py-4 md:px-6">
      <Link to="/runs" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
        <ArrowLeft className="h-3.5 w-3.5" /> Runs
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted">
            <span className="font-mono">{r.id.slice(0, 12)}</span>·<span>{r.mode}</span>·<span>{r.trigger}</span>·<span>{fmtDateTime(r.started_at)}</span>
            {r.case_id && (
              <>
                ·
                <Link to={`/cases/${r.case_id}`} className="text-accent hover:underline">
                  {r.case_number}
                </Link>
              </>
            )}
          </div>
          <h1 className="mt-1 flex items-center gap-3 text-2xl font-normal tracking-tight">
            {r.workflow_name} <StatusBadge value={r.status} />
          </h1>
        </div>
        <div className="flex gap-2">
          {(r.status === "running" || r.status === "queued") && (
            <button
              className="btn-danger"
              disabled={op.isPending}
              onClick={() => op.mutate({ id: r.id, op: "cancel" }, { onSuccess: () => toast.info("Cancel requested"), onError: (e) => toast.error("Cancel failed", errorMessage(e)) })}
            >
              <Square className="h-4 w-4" /> Cancel
            </button>
          )}
          {can("runs:debug") && r.status !== "running" && (
            <button
              className="btn-secondary"
              disabled={op.isPending}
              onClick={() =>
                op.mutate(
                  { id: r.id, op: "replay" },
                  {
                    onSuccess: (n) => {
                      toast.success("Replay started");
                      navigate(`/runs/${n.id}`);
                    },
                    onError: (e) => toast.error("Replay failed", errorMessage(e)),
                  },
                )
              }
            >
              <RotateCcw className="h-4 w-4" /> Replay
            </button>
          )}
        </div>
      </div>
      {r.handoffs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted">Handoffs:</span>
          <span className="chip">{r.handoffs[0].from}</span>
          {r.handoffs.map((h, i) => (
            <span key={i} className="flex items-center gap-1.5" title={h.reason}>
              <ArrowRight className="h-3 w-3 text-subtle" />
              <span className="chip text-accent">{h.to}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface Row {
  span: Span;
  depth: number;
  hasChildren: boolean;
}

function Trace({ r }: { r: Run }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [selId, setSelId] = useState<string | null>(null);

  const { rows, t0, total } = useMemo(() => {
    const spans = r.spans;
    const children = new Map<string | null, Span[]>();
    const ids = new Set(spans.map((s) => s.id));
    for (const s of spans) {
      const p = s.parent_id && ids.has(s.parent_id) ? s.parent_id : null;
      children.set(p, [...(children.get(p) ?? []), s]);
    }
    children.forEach((list) => list.sort((a, b) => a.started_at.localeCompare(b.started_at)));
    const out: Row[] = [];
    const walk = (parent: string | null, depth: number) => {
      for (const s of children.get(parent) ?? []) {
        const kids = children.get(s.id) ?? [];
        out.push({ span: s, depth, hasChildren: kids.length > 0 });
        if (!collapsed.has(s.id)) walk(s.id, depth + 1);
      }
    };
    walk(null, 0);
    const starts = spans.map((s) => new Date(s.started_at).getTime());
    const ends = spans.map((s) => new Date(s.started_at).getTime() + (s.duration_ms || 0));
    const t0 = starts.length ? Math.min(...starts) : Date.now();
    const t1 = ends.length ? Math.max(...ends) : t0 + 1;
    return { rows: out, t0, total: Math.max(1, t1 - t0) };
  }, [r.spans, collapsed]);

  const sel = r.spans.find((s) => s.id === selId) ?? null;

  if (!r.spans.length)
    return (
      <Card className="p-10 text-center text-sm text-muted">{r.status === "running" || r.status === "queued" ? "Waiting for the first span…" : "This run recorded no spans."}</Card>
    );

  return (
    <div className="grid gap-4 2xl:grid-cols-[1fr_420px]">
      <Card className="overflow-hidden">
        <div className="flex items-center gap-4 border-b border-line px-4 py-2.5 text-[11px] text-muted">
          {(Object.keys(KIND_COLOR) as Span["kind"][]).map((k) => (
            <span key={k} className="flex items-center gap-1.5">
              <span className={cn("h-2 w-2 rounded-sm", KIND_COLOR[k])} />
              {k}
            </span>
          ))}
          <span className="ml-auto">total {fmtMs(total)}</span>
        </div>
        <div className="scrollbar-thin max-h-[68vh] overflow-auto">
          {rows.map(({ span: s, depth, hasChildren }) => {
            const start = new Date(s.started_at).getTime() - t0;
            const left = (start / total) * 100;
            const width = Math.max(0.4, ((s.duration_ms || 0) / total) * 100);
            return (
              <div
                key={s.id}
                onClick={() => setSelId(s.id)}
                className={cn("grid cursor-pointer grid-cols-[minmax(240px,38%)_1fr] items-center border-b border-line/40 text-sm hover:bg-card2/50", selId === s.id && "bg-card2")}
              >
                <div className="flex min-w-0 items-center gap-1.5 py-1.5 pr-2" style={{ paddingLeft: 10 + depth * 16 }}>
                  {hasChildren ? (
                    <button
                      className="text-subtle hover:text-fg"
                      onClick={(e) => {
                        e.stopPropagation();
                        setCollapsed((c) => {
                          const n = new Set(c);
                          if (n.has(s.id)) n.delete(s.id);
                          else n.add(s.id);
                          return n;
                        });
                      }}
                    >
                      {collapsed.has(s.id) ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </button>
                  ) : (
                    <span className="w-3.5" />
                  )}
                  <span className={cn("text-[10px] uppercase", KIND_TEXT[s.kind])}>{s.kind}</span>
                  <span className={cn("truncate font-mono text-[12px]", s.status !== "ok" && (s.status === "error" ? "text-danger" : "text-warn"))}>{s.name}</span>
                </div>
                <div className="relative h-7 pr-3">
                  <div
                    className={cn("absolute top-1/2 h-2.5 -translate-y-1/2 rounded-sm", KIND_COLOR[s.kind], s.status === "error" && "bg-danger", s.status === "blocked" && "bg-warn")}
                    style={{ left: `${left}%`, width: `${width}%`, opacity: 0.85 }}
                  />
                  <span className="absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-[10.5px] text-muted" style={{ left: `calc(${Math.min(left + width, 88)}% + 6px)` }}>
                    {fmtMs(s.duration_ms)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
      <Card className="h-fit 2xl:sticky 2xl:top-4">
        {!sel ? (
          <p className="p-8 text-center text-sm text-muted">Select a span to inspect its input, output and attributes.</p>
        ) : (
          <>
            <CardHeader title={<span className="font-mono text-sm">{sel.name}</span>} subtitle={`${sel.kind}${sel.agent_id ? ` · ${sel.agent_id}` : ""}`} right={<StatusBadge value={sel.status} />} />
            <div className="space-y-4 p-5 pt-3">
              <div>
                <Kv k="Started" v={`${fmtDateTime(sel.started_at)} (${relTime(sel.started_at)})`} />
                <Kv k="Duration" v={fmtMs(sel.duration_ms)} />
                {(sel.tokens_in > 0 || sel.tokens_out > 0) && <Kv k="Tokens in / out" v={`${fmtNum(sel.tokens_in)} / ${fmtNum(sel.tokens_out)}`} />}
              </div>
              {sel.error && (
                <div className="rounded-lg border border-danger/30 bg-danger/5 p-3">
                  <div className="text-xs text-danger">Error</div>
                  <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[11.5px]">{sel.error}</pre>
                </div>
              )}
              {sel.input_preview && <Preview label="Input" text={sel.input_preview} />}
              {sel.output_preview && <Preview label="Output" text={sel.output_preview} />}
              {Object.keys(sel.attributes ?? {}).length > 0 && (
                <div>
                  <div className="label">Attributes</div>
                  <JsonView value={sel.attributes} maxHeight="max-h-[260px]" />
                </div>
              )}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

function Preview({ label, text }: { label: string; text: string }) {
  let pretty = text;
  try {
    pretty = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    /* plain text */
  }
  return (
    <div>
      <div className="label">{label}</div>
      <pre className="scrollbar-thin max-h-[240px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-deep p-3 font-mono text-[11.5px] text-fg/85">{pretty}</pre>
    </div>
  );
}
