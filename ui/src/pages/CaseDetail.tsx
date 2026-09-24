import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Bot, ChevronDown, ClipboardCheck, MessageSquare, Play, Radio, Send, UserRound } from "lucide-react";
import { useAddComment, useCase, useRunCaseWorkflow, useUpdateCase, useUsers, useWorkflows } from "@/api/hooks";
import type { CaseDetail as CaseT, CaseStatus, Severity } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Card, CardHeader, EmptyState, ErrorState, Markdown, SeverityBadge, Select, SkeletonRows, Spinner, StatusBadge, Tabs, DataTable, type Column } from "@/components/ui";
import { ActionCard } from "@/components/ActionCard";
import { RunsTable } from "@/components/RunsTable";
import { fmtDateTime, fmtPct, relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/cn";
import type { Alert } from "@/api/types";

type Tab = "overview" | "timeline" | "findings" | "actions" | "runs" | "alerts";
const STATUSES: CaseStatus[] = ["open", "triage", "investigating", "contained", "resolved", "closed", "false_positive"];
const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "informational"];

export default function CaseDetail() {
  const { id = "" } = useParams();
  const q = useCase(id);
  const [tab, setTab] = useState<Tab>("overview");

  if (q.isLoading) return <SkeletonRows rows={10} />;
  if (q.error || !q.data) return <ErrorState error={q.error ?? "Not found"} onRetry={() => q.refetch()} />;
  const c = q.data;

  return (
    <div>
      <CaseHeader c={c} />
      <div className="px-4 md:px-6">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "overview", label: "Overview" },
            { value: "timeline", label: "Timeline", count: c.timeline.length },
            { value: "findings", label: "Findings", count: c.findings.length },
            { value: "actions", label: "Actions", count: c.actions.length },
            { value: "runs", label: "Agent runs", count: c.runs.length },
            { value: "alerts", label: "Alerts", count: c.alerts.length },
          ]}
        />
      </div>
      <div className="grid gap-4 p-4 md:p-6 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-4">
          {tab === "overview" && <Overview c={c} onTab={setTab} />}
          {tab === "timeline" && <Timeline c={c} />}
          {tab === "findings" && <Findings c={c} />}
          {tab === "actions" && (
            <div className="space-y-3">
              {c.actions.length ? c.actions.map((a) => <ActionCard key={a.id} a={a} compact />) : <Card><EmptyState icon={<ClipboardCheck className="h-5 w-5" />} title="No response actions" body="The response planner hasn't proposed any actions for this incident." /></Card>}
            </div>
          )}
          {tab === "runs" && (
            <Card>
              <RunsTable runs={c.runs} hideCase />
            </Card>
          )}
          {tab === "alerts" && <CaseAlerts alerts={c.alerts} />}
        </div>
        <Comments c={c} />
      </div>
    </div>
  );
}

function CaseHeader({ c }: { c: CaseT }) {
  const { can } = useAuth();
  const upd = useUpdateCase(c.id);
  const users = useUsers();
  const toast = useToast();
  const editable = can("cases:write");
  const patch = (body: Parameters<typeof upd.mutate>[0]) =>
    upd.mutate(body, { onSuccess: () => toast.success("Incident updated"), onError: (e) => toast.error("Update failed", errorMessage(e)) });

  return (
    <div className="border-b border-line px-4 py-4 md:px-6">
      <Link to="/cases" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
        <ArrowLeft className="h-3.5 w-3.5" /> Incidents
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm text-muted">
            <span className="font-mono">{c.number}</span>·<span>opened {relTime(c.created_at)}</span>·<span>confidence {fmtPct(c.confidence, 0, true)}</span>
          </div>
          <h1 className="mt-1 text-2xl font-normal tracking-tight">{c.title}</h1>
        </div>
        <RunWorkflowMenu caseId={c.id} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {editable ? (
          <>
            <Select className="w-40" value={c.severity} onChange={(v) => patch({ severity: v as Severity })} options={SEVERITIES.map((s) => ({ value: s, label: `Severity: ${s}` }))} />
            <Select className="w-48" value={c.status} onChange={(v) => patch({ status: v as CaseStatus })} options={STATUSES.map((s) => ({ value: s, label: `Status: ${s.replace("_", " ")}` }))} />
            <Select
              className="w-52"
              value={c.assignee?.id ?? ""}
              onChange={(v) => patch({ assignee_id: v || null })}
              options={[{ value: "", label: "Unassigned" }, ...(users.data ?? []).map((u) => ({ value: u.id, label: u.name })), ...(c.assignee && !(users.data ?? []).some((u) => u.id === c.assignee?.id) ? [{ value: c.assignee.id, label: c.assignee.name }] : [])]}
            />
            {upd.isPending && <Spinner />}
          </>
        ) : (
          <>
            <SeverityBadge value={c.severity} />
            <StatusBadge value={c.status} />
            <span className="text-sm text-muted">{c.assignee?.name ?? "Unassigned"}</span>
          </>
        )}
      </div>
    </div>
  );
}

function RunWorkflowMenu({ caseId }: { caseId: string }) {
  const { can } = useAuth();
  const wfs = useWorkflows();
  const run = useRunCaseWorkflow(caseId);
  const toast = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  if (!can("workflows:run")) return null;
  return (
    <div className="relative" ref={ref}>
      <button className="btn-primary" onClick={() => setOpen(!open)} disabled={run.isPending}>
        {run.isPending ? <Spinner className="text-black" /> : <Play className="h-4 w-4" />} Run workflow <ChevronDown className="h-4 w-4" />
      </button>
      {open && (
        <div className="card absolute right-0 top-11 z-40 w-72 bg-card p-1.5 shadow-2xl">
          {(wfs.data ?? [])
            .filter((w) => w.enabled)
            .map((w) => (
              <button
                key={w.id}
                className="w-full rounded-md px-3 py-2 text-left hover:bg-card2"
                onClick={() => {
                  setOpen(false);
                  run.mutate(w.id, {
                    onSuccess: (r) => {
                      toast.success("Workflow started", w.name);
                      navigate(`/runs/${r.id}`);
                    },
                    onError: (e) => toast.error("Couldn't start workflow", errorMessage(e)),
                  });
                }}
              >
                <div className="text-sm">{w.name}</div>
                <div className="text-[11px] text-muted">
                  {w.mode} · entry {w.entry_agent}
                </div>
              </button>
            ))}
          {!wfs.data?.length && <div className="px-3 py-3 text-sm text-muted">No workflows available.</div>}
        </div>
      )}
    </div>
  );
}

function Overview({ c, onTab }: { c: CaseT; onTab: (t: Tab) => void }) {
  const roleTone: Record<string, string> = { attacker: "text-danger", victim: "text-accent", observed: "text-muted" };
  return (
    <>
      <Card>
        <CardHeader title="Summary" />
        <div className="px-5 pb-5 pt-2">
          <Markdown>{c.summary}</Markdown>
          {c.mitre.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {c.mitre.map((m) => (
                <span key={m.technique_id} className="chip">
                  <span className="font-mono text-accent">{m.technique_id}</span> {m.name}
                  <span className="text-subtle">· {m.tactic}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Entities" subtitle={`${c.entities.length} extracted`} />
          <div className="px-5 pb-4 pt-2">
            {!c.entities.length && <p className="py-4 text-sm text-muted">No entities.</p>}
            {c.entities.map((e, i) => (
              <div key={i} className="flex items-center justify-between gap-3 border-b border-line/60 py-2 text-sm last:border-0">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="chip w-16 justify-center">{e.type}</span>
                  <span className="truncate font-mono text-[13px]">{e.value}</span>
                </span>
                <span className={cn("text-xs", roleTone[e.role])}>{e.role}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="At a glance" />
          <div className="grid grid-cols-2 gap-3 p-5 pt-3">
            {[
              { icon: Radio, label: "Alerts", v: c.alert_count, t: "alerts" as Tab },
              { icon: AlertTriangle, label: "Findings", v: c.findings.length, t: "findings" as Tab },
              { icon: ClipboardCheck, label: "Pending actions", v: c.pending_actions, t: "actions" as Tab },
              { icon: Bot, label: "Agents involved", v: c.agents_involved.length, t: "runs" as Tab },
            ].map((x) => (
              <button key={x.label} onClick={() => onTab(x.t)} className="rounded-lg border border-line bg-card2/40 p-3 text-left hover:border-subtle/60">
                <x.icon className="h-4 w-4 text-accent" />
                <div className="mt-2 text-xl">{x.v}</div>
                <div className="text-xs text-muted">{x.label}</div>
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5 px-5 pb-5">
            {c.agents_involved.map((a) => (
              <Link key={a} to={`/agents/${a}`} className="chip hover:text-fg">
                <Bot className="h-3 w-3" /> {a}
              </Link>
            ))}
          </div>
        </Card>
      </div>
      {c.findings[0] && (
        <Card>
          <CardHeader title={`Latest finding · ${c.findings[0].title}`} subtitle={`${c.findings[0].agent} · ${relTime(c.findings[0].created_at)}`} />
          <div className="px-5 pb-5 pt-2">
            <Markdown>{c.findings[0].body_md}</Markdown>
          </div>
        </Card>
      )}
    </>
  );
}

function Timeline({ c }: { c: CaseT }) {
  const icon = { alert: Radio, agent: Bot, action: ClipboardCheck, comment: MessageSquare, status: AlertTriangle } as const;
  const color = { alert: "text-accent", agent: "text-info", action: "text-success", comment: "text-muted", status: "text-warn" } as const;
  const items = [...c.timeline].sort((a, b) => b.ts.localeCompare(a.ts));
  return (
    <Card className="p-5">
      {!items.length && <EmptyState title="No timeline events" />}
      <ol className="relative ml-3 border-l border-line">
        {items.map((t, i) => {
          const I = icon[t.kind] ?? Radio;
          return (
            <li key={i} className="mb-5 ml-5 last:mb-0">
              <span className="absolute -left-[13px] flex h-6 w-6 items-center justify-center rounded-full border border-line bg-card">
                <I className={cn("h-3.5 w-3.5", color[t.kind])} />
              </span>
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm">{t.text}</span>
              </div>
              <div className="mt-0.5 text-[11px] text-subtle">
                {t.actor} · {fmtDateTime(t.ts)}
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function Findings({ c }: { c: CaseT }) {
  if (!c.findings.length)
    return (
      <Card>
        <EmptyState title="No findings yet" body="Agents record findings as they investigate." />
      </Card>
    );
  return (
    <div className="space-y-3">
      {c.findings.map((f) => (
        <Card key={f.id}>
          <CardHeader title={f.title} subtitle={`${f.agent} · ${fmtDateTime(f.created_at)}`} />
          <div className="px-5 pb-5 pt-2">
            <Markdown>{f.body_md}</Markdown>
            {f.standard_refs.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {f.standard_refs.map((s) => (
                  <span key={s} className="chip font-mono">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}

function CaseAlerts({ alerts }: { alerts: Alert[] }) {
  const cols: Column<Alert>[] = [
    { key: "ts", header: "Time", cell: (a) => fmtDateTime(a.ts), sort: (a) => a.ts },
    { key: "sev", header: "Severity", cell: (a) => <SeverityBadge value={a.severity} /> },
    { key: "rule", header: "Rule", cell: (a) => <span className="line-clamp-1">{a.rule_description}</span> },
    { key: "agent", header: "Endpoint", cell: (a) => a.agent_name },
    { key: "src", header: "Source", cell: (a) => <span className="font-mono text-xs">{a.src_ip ?? "—"}</span> },
  ];
  return (
    <Card>
      <DataTable rows={alerts} columns={cols} rowKey={(a) => a.id} initialSort={{ key: "ts", dir: "desc" }} />
    </Card>
  );
}

function Comments({ c }: { c: CaseT }) {
  const { can } = useAuth();
  const add = useAddComment(c.id);
  const toast = useToast();
  const [body, setBody] = useState("");
  return (
    <Card className="h-fit xl:sticky xl:top-4">
      <CardHeader title="Discussion" subtitle={`${c.comments.length} comments`} />
      <div className="scrollbar-thin max-h-[420px] space-y-3 overflow-y-auto px-5 py-3">
        {!c.comments.length && <p className="text-sm text-muted">No comments yet.</p>}
        {c.comments.map((m) => (
          <div key={m.id} className="flex gap-2.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-card2">
              <UserRound className="h-3.5 w-3.5 text-muted" />
            </span>
            <div className="min-w-0">
              <div className="text-xs">
                {m.author.name} <span className="text-subtle">· {relTime(m.created_at)}</span>
              </div>
              <div className="mt-0.5 whitespace-pre-wrap break-words text-sm text-fg/90">{m.body}</div>
            </div>
          </div>
        ))}
      </div>
      {can("cases:write") && (
        <form
          className="flex items-end gap-2 border-t border-line p-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!body.trim()) return;
            add.mutate(body.trim(), { onSuccess: () => setBody(""), onError: (er) => toast.error("Comment failed", errorMessage(er)) });
          }}
        >
          <textarea className="textarea min-h-[38px]" rows={2} placeholder="Add a note for the team…" value={body} onChange={(e) => setBody(e.target.value)} />
          <button className="btn-primary h-[38px] px-3" disabled={add.isPending || !body.trim()} aria-label="Send">
            <Send className="h-4 w-4" />
          </button>
        </form>
      )}
    </Card>
  );
}
