import { useState } from "react";
import { Bot, Cog, Search, User } from "lucide-react";
import { useAudit } from "@/api/hooks";
import type { AuditEntry } from "@/api/types";
import { Async, Card, DataTable, Drawer, JsonView, Kv, PageBody, PageHeader, Select, type Column } from "@/components/ui";
import { fmtDateTime, relTime } from "@/lib/format";

export default function Audit() {
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [since, setSince] = useState("");
  const [applied, setApplied] = useState({ actor: "", action: "" });
  const q = useAudit({ actor: applied.actor || undefined, action: applied.action || undefined, since: since ? new Date(Date.now() - Number(since) * 3600_000).toISOString() : undefined });
  const [sel, setSel] = useState<AuditEntry | null>(null);
  const cols: Column<AuditEntry>[] = [
    { key: "ts", header: "Time", cell: (e) => <span className="whitespace-nowrap text-muted">{fmtDateTime(e.ts)}</span>, sort: (e) => e.ts },
    {
      key: "actor",
      header: "Actor",
      cell: (e) => (
        <span className="flex items-center gap-2 whitespace-nowrap">
          {e.actor.type === "user" ? <User className="h-3.5 w-3.5 text-muted" /> : e.actor.type === "agent" ? <Bot className="h-3.5 w-3.5 text-accent" /> : <Cog className="h-3.5 w-3.5 text-info" />}
          {e.actor.name}
        </span>
      ),
      sort: (e) => e.actor.name,
    },
    { key: "action", header: "Action", cell: (e) => <span className="font-mono text-xs">{e.action}</span>, sort: (e) => e.action },
    { key: "target", header: "Target", cell: (e) => <span className="line-clamp-1 max-w-[320px]">{e.target}</span> },
    { key: "ip", header: "IP", cell: (e) => <span className="font-mono text-xs text-muted">{e.ip ?? "—"}</span> },
  ];
  return (
    <div>
      <PageHeader title="Audit Log" subtitle="Immutable record of every human, agent and system action" />
      <PageBody>
        <Card>
          <form
            className="flex flex-wrap items-center gap-2 border-b border-line p-3"
            onSubmit={(e) => {
              e.preventDefault();
              setApplied({ actor: actor.trim(), action: action.trim() });
            }}
          >
            <div className="relative min-w-[180px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
              <input className="input pl-9" placeholder="Actor" value={actor} onChange={(e) => setActor(e.target.value)} />
            </div>
            <input className="input max-w-[220px]" placeholder="Action (e.g. action.approved)" value={action} onChange={(e) => setAction(e.target.value)} />
            <Select className="w-36" value={since} onChange={setSince} options={[{ value: "", label: "All time" }, { value: "1", label: "Last hour" }, { value: "24", label: "Last 24h" }, { value: "168", label: "Last 7 days" }]} />
            <button className="btn-secondary">Apply</button>
          </form>
          <Async q={q}>{(d) => <DataTable rows={d.items} columns={cols} rowKey={(e) => e.id} onRowClick={setSel} initialSort={{ key: "ts", dir: "desc" }} />}</Async>
        </Card>
      </PageBody>
      <Drawer open={!!sel} onClose={() => setSel(null)} title={sel?.action ?? ""} subtitle={sel ? relTime(sel.ts) : undefined}>
        {sel && (
          <div className="space-y-4">
            <div>
              <Kv k="Time" v={fmtDateTime(sel.ts)} />
              <Kv k="Actor" v={`${sel.actor.name} (${sel.actor.type})`} />
              <Kv k="Target" v={sel.target} />
              <Kv k="Source IP" v={sel.ip ?? "—"} />
            </div>
            <JsonView value={sel.detail} />
          </div>
        )}
      </Drawer>
    </div>
  );
}
