import { useNavigate } from "react-router-dom";
import type { RunSummary } from "@/api/types";
import { DataTable, StatusBadge, type Column } from "./ui";
import { fmtMs, fmtNum, fmtUsd, relTime } from "@/lib/format";

export function RunsTable({ runs, hideCase }: { runs: RunSummary[]; hideCase?: boolean }) {
  const navigate = useNavigate();
  const cols: Column<RunSummary>[] = [
    { key: "started", header: "Started", cell: (r) => <span className="whitespace-nowrap text-muted">{relTime(r.started_at)}</span>, sort: (r) => r.started_at },
    {
      key: "wf",
      header: "Workflow",
      cell: (r) => (
        <div>
          <div className="whitespace-nowrap">{r.workflow_name}</div>
          <div className="text-[11px] text-subtle">
            {r.mode} · {r.trigger}
          </div>
        </div>
      ),
      sort: (r) => r.workflow_name,
    },
    { key: "status", header: "Status", cell: (r) => <StatusBadge value={r.status} />, sort: (r) => r.status },
    {
      key: "agents",
      header: "Agents",
      cell: (r) => (
        <div className="flex max-w-[260px] flex-wrap gap-1">
          {r.agents.slice(0, 4).map((a) => (
            <span key={a} className="chip">
              {a}
            </span>
          ))}
          {r.agents.length > 4 && <span className="chip">+{r.agents.length - 4}</span>}
        </div>
      ),
    },
    ...(hideCase ? [] : [{ key: "case", header: "Incident", cell: (r: RunSummary) => <span className="font-mono text-xs text-muted">{r.case_number ?? "—"}</span> }]),
    { key: "dur", header: "Duration", cell: (r) => fmtMs(r.duration_ms), sort: (r) => r.duration_ms ?? 0 },
    { key: "tools", header: "Tool calls", cell: (r) => r.tool_calls, sort: (r) => r.tool_calls },
    { key: "tokens", header: "Tokens", cell: (r) => fmtNum(r.tokens_in + r.tokens_out), sort: (r) => r.tokens_in + r.tokens_out },
    { key: "cost", header: "Cost", cell: (r) => fmtUsd(r.cost_usd), sort: (r) => r.cost_usd },
    { key: "err", header: "Errors", cell: (r) => (r.errors ? <span className="text-danger">{r.errors}</span> : <span className="text-subtle">0</span>), sort: (r) => r.errors },
  ];
  return <DataTable rows={runs} columns={cols} rowKey={(r) => r.id} onRowClick={(r) => navigate(`/runs/${r.id}`)} initialSort={{ key: "started", dir: "desc" }} empty={<p className="p-8 text-center text-sm text-muted">No runs yet.</p>} />;
}
