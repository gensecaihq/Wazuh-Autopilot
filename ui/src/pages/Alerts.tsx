import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Play, Search } from "lucide-react";
import { useAlert, useAlerts, useTriageAlert } from "@/api/hooks";
import type { Alert } from "@/api/types";
import { Async, Card, DataTable, Drawer, JsonView, Kv, PageBody, PageHeader, Select, SeverityBadge, Spinner, StatusBadge, type Column } from "@/components/ui";
import { fmtDateTime, relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { errorMessage } from "@/api/client";

const SEV = ["", "critical", "high", "medium", "low", "informational"];
const STATUS = ["", "new", "triaged", "grouped", "suppressed"];

export default function Alerts() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const severity = sp.get("severity") ?? "";
  const status = sp.get("status") ?? "";
  const list = useAlerts({ q: sp.get("q") ?? undefined, severity, status });
  const [openId, setOpenId] = useState<string | null>(null);

  const setParam = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    setSp(n, { replace: true });
  };

  const cols: Column<Alert>[] = [
    { key: "ts", header: "Time", cell: (a) => <span className="whitespace-nowrap text-muted">{relTime(a.ts)}</span>, sort: (a) => a.ts },
    { key: "sev", header: "Severity", cell: (a) => <SeverityBadge value={a.severity} />, sort: (a) => a.rule_level },
    {
      key: "rule",
      header: "Rule",
      cell: (a) => (
        <div className="min-w-0">
          <div className="max-w-[420px] truncate">{a.rule_description}</div>
          <div className="text-[11px] text-subtle">
            rule {a.rule_id} · level {a.rule_level}
            {a.mitre[0] && <> · {a.mitre[0].technique_id}</>}
          </div>
        </div>
      ),
      sort: (a) => a.rule_description,
    },
    { key: "agent", header: "Endpoint", cell: (a) => <span className="whitespace-nowrap">{a.agent_name}</span>, sort: (a) => a.agent_name },
    { key: "src", header: "Source", cell: (a) => <span className="font-mono text-xs">{a.src_ip ?? "—"}</span> },
    { key: "status", header: "Status", cell: (a) => <StatusBadge value={a.status} />, sort: (a) => a.status },
    {
      key: "case",
      header: "Incident",
      cell: (a) =>
        a.case_id ? (
          <Link to={`/cases/${a.case_id}`} onClick={(e) => e.stopPropagation()} className="text-accent hover:underline">
            view
          </Link>
        ) : (
          <span className="text-subtle">—</span>
        ),
    },
  ];

  return (
    <div>
      <PageHeader title="Alerts" subtitle="Wazuh alerts ingested by polling or webhook" />
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
              <input className="input pl-9" placeholder="Search rule, endpoint, IP, user…" value={q} onChange={(e) => setQ(e.target.value)} />
            </form>
            <Select className="w-40" value={severity} onChange={(v) => setParam("severity", v)} options={SEV.map((s) => ({ value: s, label: s ? s : "All severities" }))} />
            <Select className="w-36" value={status} onChange={(v) => setParam("status", v)} options={STATUS.map((s) => ({ value: s, label: s ? s : "All statuses" }))} />
            <span className="ml-auto text-xs text-muted">{list.data ? `${list.data.total.toLocaleString()} alerts` : ""}</span>
          </div>
          <Async q={list}>{(d) => <DataTable rows={d.items} columns={cols} rowKey={(a) => a.id} onRowClick={(a) => setOpenId(a.id)} initialSort={{ key: "ts", dir: "desc" }} />}</Async>
        </Card>
      </PageBody>
      <AlertDrawer id={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}

function AlertDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const q = useAlert(id ?? undefined);
  const triage = useTriageAlert();
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const a = q.data;
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      title={a?.rule_description ?? "Alert"}
      subtitle={a ? `${a.agent_name} · ${fmtDateTime(a.ts)}` : undefined}
      footer={
        can("workflows:run") && a ? (
          <button
            className="btn-primary"
            disabled={triage.isPending}
            onClick={() =>
              triage.mutate(a.id, {
                onSuccess: (run) => {
                  toast.success("Triage started", `Run ${run.id.slice(0, 8)} is working this alert.`);
                  navigate(`/runs/${run.id}`);
                },
                onError: (e) => toast.error("Couldn't start triage", errorMessage(e)),
              })
            }
          >
            {triage.isPending ? <Spinner className="text-black" /> : <Play className="h-4 w-4" />} Run triage
          </button>
        ) : undefined
      }
    >
      {q.isLoading && <Spinner />}
      {a && (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <SeverityBadge value={a.severity} />
            <StatusBadge value={a.status} />
            {a.rule_groups.map((g) => (
              <span key={g} className="chip">
                {g}
              </span>
            ))}
          </div>
          <div>
            <Kv k="Rule" v={`${a.rule_id} (level ${a.rule_level})`} />
            <Kv k="Endpoint" v={`${a.agent_name} (${a.agent_id})`} />
            <Kv k="Source IP" v={a.src_ip ? `${a.src_ip}${a.src_country ? ` · ${a.src_country}` : ""}` : "—"} />
            <Kv k="User" v={a.dst_user ?? "—"} />
            <Kv k="Wazuh ID" v={<span className="font-mono text-xs">{a.wazuh_id}</span>} />
            {a.case_id && (
              <Kv
                k="Incident"
                v={
                  <Link to={`/cases/${a.case_id}`} className="text-accent hover:underline">
                    Open incident
                  </Link>
                }
              />
            )}
          </div>
          {a.mitre.length > 0 && (
            <div>
              <div className="label">MITRE ATT&CK</div>
              <div className="flex flex-wrap gap-1.5">
                {a.mitre.map((m) => (
                  <span key={m.technique_id} className="chip">
                    <span className="font-mono text-accent">{m.technique_id}</span> {m.name} · {m.tactic}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div>
            <div className="label">Raw Wazuh alert</div>
            <JsonView value={a.raw ?? a} />
          </div>
        </div>
      )}
    </Drawer>
  );
}
