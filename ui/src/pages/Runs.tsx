import { useSearchParams } from "react-router-dom";
import { useAgents, useRuns, useWorkflows } from "@/api/hooks";
import { Async, Card, PageBody, PageHeader, Select } from "@/components/ui";
import { RunsTable } from "@/components/RunsTable";

export default function Runs() {
  const [sp, setSp] = useSearchParams();
  const status = sp.get("status") ?? "";
  const workflow_id = sp.get("workflow_id") ?? "";
  const agent_id = sp.get("agent_id") ?? "";
  const runs = useRuns({ status, workflow_id, agent_id });
  const wfs = useWorkflows();
  const agents = useAgents();
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    setSp(n, { replace: true });
  };
  return (
    <div>
      <PageHeader title="Runs & Traces" subtitle="Every swarm, graph and playground execution with full span traces" />
      <PageBody>
        <Card>
          <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
            <Select className="w-40" value={status} onChange={(v) => set("status", v)} options={["", "queued", "running", "completed", "failed", "cancelled"].map((s) => ({ value: s, label: s || "All statuses" }))} />
            <Select className="w-56" value={workflow_id} onChange={(v) => set("workflow_id", v)} options={[{ value: "", label: "All workflows" }, ...(wfs.data ?? []).map((w) => ({ value: w.id, label: w.name }))]} />
            <Select className="w-48" value={agent_id} onChange={(v) => set("agent_id", v)} options={[{ value: "", label: "All agents" }, ...(agents.data ?? []).map((a) => ({ value: a.id, label: a.codename }))]} />
            <span className="ml-auto text-xs text-muted">{runs.data ? `${runs.data.total} runs` : ""}</span>
          </div>
          <Async q={runs}>{(d) => <RunsTable runs={d.items} />}</Async>
        </Card>
      </PageBody>
    </div>
  );
}
