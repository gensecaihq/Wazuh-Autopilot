import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Columns3, List, Search } from "lucide-react";
import { useCases } from "@/api/hooks";
import type { Case, CaseStatus } from "@/api/types";
import { Async, Card, DataTable, PageBody, PageHeader, Segmented, Select, SeverityBadge, StatusBadge, type Column } from "@/components/ui";
import { fmtPct, relTime } from "@/lib/format";
import { cn } from "@/lib/cn";

const STATUSES: CaseStatus[] = ["open", "triage", "investigating", "contained", "resolved", "closed", "false_positive"];
const KANBAN: CaseStatus[] = ["open", "triage", "investigating", "contained", "resolved"];

export default function Cases() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [view, setView] = useState<"table" | "board">("table");
  const status = sp.get("status") ?? "";
  const severity = sp.get("severity") ?? "";
  const list = useCases({ q: sp.get("q") ?? undefined, status, severity });
  const navigate = useNavigate();

  const setParam = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    setSp(n, { replace: true });
  };

  const cols: Column<Case>[] = [
    { key: "num", header: "ID", cell: (c) => <span className="font-mono text-xs text-muted">{c.number}</span>, sort: (c) => c.number },
    {
      key: "title",
      header: "Incident",
      cell: (c) => (
        <div className="min-w-0">
          <div className="max-w-[440px] truncate">{c.title}</div>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {c.mitre.slice(0, 3).map((m) => (
              <span key={m.technique_id} className="font-mono text-[10.5px] text-subtle">
                {m.technique_id}
              </span>
            ))}
          </div>
        </div>
      ),
      sort: (c) => c.title,
    },
    { key: "sev", header: "Severity", cell: (c) => <SeverityBadge value={c.severity} />, sort: (c) => ["informational", "low", "medium", "high", "critical"].indexOf(c.severity) },
    { key: "status", header: "Status", cell: (c) => <StatusBadge value={c.status} />, sort: (c) => STATUSES.indexOf(c.status) },
    { key: "conf", header: "Confidence", cell: (c) => fmtPct(c.confidence, 0, true), sort: (c) => c.confidence },
    { key: "alerts", header: "Alerts", cell: (c) => c.alert_count, sort: (c) => c.alert_count },
    {
      key: "pending",
      header: "Actions",
      cell: (c) =>
        c.pending_actions ? <span className="rounded-md border border-accent/30 bg-accent/10 px-1.5 text-xs text-accent">{c.pending_actions} pending</span> : <span className="text-subtle">—</span>,
      sort: (c) => c.pending_actions,
    },
    { key: "assignee", header: "Assignee", cell: (c) => c.assignee?.name ?? <span className="text-subtle">Unassigned</span> },
    { key: "updated", header: "Updated", cell: (c) => <span className="whitespace-nowrap text-muted">{relTime(c.updated_at)}</span>, sort: (c) => c.updated_at },
  ];

  return (
    <div>
      <PageHeader
        title="Incidents"
        subtitle="Cases opened by the swarm from correlated Wazuh alerts"
        right={
          <Segmented
            value={view}
            onChange={setView}
            options={[
              { value: "table", label: <List className="h-4 w-4" /> },
              { value: "board", label: <Columns3 className="h-4 w-4" /> },
            ]}
          />
        }
      />
      <PageBody>
        <Card>
          <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
            <form
              className="relative min-w-[220px] flex-1"
              onSubmit={(e) => {
                e.preventDefault();
                setParam("q", q.trim());
              }}
            >
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
              <input className="input pl-9" placeholder="Search incidents…" value={q} onChange={(e) => setQ(e.target.value)} />
            </form>
            <Select className="w-40" value={severity} onChange={(v) => setParam("severity", v)} options={["", "critical", "high", "medium", "low"].map((s) => ({ value: s, label: s || "All severities" }))} />
            {view === "table" && (
              <Select className="w-40" value={status} onChange={(v) => setParam("status", v)} options={["", ...STATUSES].map((s) => ({ value: s, label: s ? s.replace("_", " ") : "All statuses" }))} />
            )}
          </div>
          <Async q={list}>
            {(d) =>
              view === "table" ? (
                <DataTable rows={d.items} columns={cols} rowKey={(c) => c.id} onRowClick={(c) => navigate(`/cases/${c.id}`)} initialSort={{ key: "updated", dir: "desc" }} />
              ) : (
                <Board cases={d.items} />
              )
            }
          </Async>
        </Card>
      </PageBody>
    </div>
  );
}

function Board({ cases }: { cases: Case[] }) {
  return (
    <div className="scrollbar-thin grid auto-cols-[minmax(250px,1fr)] grid-flow-col gap-3 overflow-x-auto p-3">
      {KANBAN.map((s) => {
        const items = cases.filter((c) => c.status === s);
        return (
          <div key={s} className="rounded-xl border border-line bg-deep/40">
            <div className="flex items-center justify-between px-3 py-2.5">
              <StatusBadge value={s} />
              <span className="text-xs text-muted">{items.length}</span>
            </div>
            <div className="space-y-2 p-2 pt-0">
              {items.map((c) => (
                <Link key={c.id} to={`/cases/${c.id}`} className={cn("block rounded-lg border border-line bg-card p-3 transition hover:border-subtle/60")}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-muted">{c.number}</span>
                    <SeverityBadge value={c.severity} />
                  </div>
                  <div className="mt-1.5 line-clamp-2 text-sm">{c.title}</div>
                  <div className="mt-2 flex items-center justify-between text-[11px] text-subtle">
                    <span>{c.alert_count} alerts</span>
                    <span>{relTime(c.updated_at)}</span>
                  </div>
                  {c.pending_actions > 0 && <div className="mt-2 text-[11px] text-accent">{c.pending_actions} action(s) awaiting approval</div>}
                </Link>
              ))}
              {!items.length && <div className="py-6 text-center text-xs text-subtle">Empty</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
