import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GitBranch, Play, Save, Waypoints } from "lucide-react";
import { useAgents, useRuns, useRunWorkflow, useSaveWorkflow, useWorkflows } from "@/api/hooks";
import type { Severity, Workflow } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Async, Badge, Card, CardHeader, Field, Modal, PageBody, PageHeader, Select, Spinner, TagInput, Toggle } from "@/components/ui";
import { DagGraph } from "@/components/Graph";
import { RunsTable } from "@/components/RunsTable";
import { fmtPct, relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/cn";

export default function Workflows() {
  const q = useWorkflows();
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => {
    if (!sel && q.data?.length) setSel(q.data[0].id);
  }, [q.data, sel]);
  const wf = q.data?.find((w) => w.id === sel);

  return (
    <div>
      <PageHeader title="Workflows" subtitle="Swarm and graph playbooks that turn alerts into investigated, contained incidents" />
      <PageBody>
        <Async q={q}>
          {(list) => (
            <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
              <div className="space-y-2">
                {list.map((w) => (
                  <button
                    key={w.id}
                    onClick={() => setSel(w.id)}
                    className={cn("card block w-full p-4 text-left transition", sel === w.id ? "border-accent/50 ring-1 ring-accent/20" : "hover:border-subtle/60")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 text-sm">
                        {w.mode === "swarm" ? <Waypoints className="h-4 w-4 text-accent" /> : <GitBranch className="h-4 w-4 text-info" />}
                        {w.name}
                      </span>
                      {!w.enabled && <Badge>off</Badge>}
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-xs text-muted">{w.description}</p>
                    <div className="mt-2 flex gap-3 text-[11px] text-subtle">
                      <span>{w.trigger.type}</span>
                      <span>{w.runs_7d} runs/7d</span>
                      <span>{fmtPct(w.success_rate, 0, true)} success</span>
                    </div>
                  </button>
                ))}
              </div>
              {wf && <WorkflowDetail key={wf.id} wf={wf} />}
            </div>
          )}
        </Async>
      </PageBody>
    </div>
  );
}

function WorkflowDetail({ wf }: { wf: Workflow }) {
  const agents = useAgents();
  const byId = useMemo(() => new Map((agents.data ?? []).map((a) => [a.id, a])), [agents.data]);
  const runs = useRuns({ workflow_id: wf.id, limit: 10 });
  const { can } = useAuth();
  const save = useSaveWorkflow();
  const toast = useToast();
  const [enabled, setEnabled] = useState(wf.enabled);
  const [trigger, setTrigger] = useState(wf.trigger);
  const [runOpen, setRunOpen] = useState(false);
  const editable = can("workflows:write");
  const dirty = enabled !== wf.enabled || JSON.stringify(trigger) !== JSON.stringify(wf.trigger);

  return (
    <div className="min-w-0 space-y-4">
      <Card glow>
        <CardHeader
          title={wf.name}
          subtitle={`${wf.mode === "swarm" ? "Swarm: agents hand off autonomously" : "Graph: deterministic DAG"} · entry ${byId.get(wf.entry_agent)?.codename ?? wf.entry_agent} · last run ${relTime(wf.last_run_at)}`}
          right={
            can("workflows:run") && (
              <button className="btn-primary" onClick={() => setRunOpen(true)} disabled={!wf.enabled}>
                <Play className="h-4 w-4" /> Run
              </button>
            )
          }
        />
        <p className="px-5 pt-2 text-sm text-muted">{wf.description}</p>
        <div className="p-4">
          <DagGraph steps={wf.steps} agents={byId} entry={wf.entry_agent} mode={wf.mode} />
        </div>
      </Card>
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[15px]">Trigger</h3>
          <Toggle checked={enabled} onChange={setEnabled} disabled={!editable} label={enabled ? "Enabled" : "Disabled"} />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Type">
            <Select
              value={trigger.type}
              disabled={!editable}
              onChange={(v) => setTrigger({ ...trigger, type: v as Workflow["trigger"]["type"] })}
              options={[
                { value: "alert", label: "On new alert" },
                { value: "schedule", label: "On schedule" },
                { value: "manual", label: "Manual only" },
              ]}
            />
          </Field>
          {trigger.type === "alert" && (
            <>
              <Field label="Minimum severity">
                <Select
                  value={trigger.severity_min ?? "high"}
                  disabled={!editable}
                  onChange={(v) => setTrigger({ ...trigger, severity_min: v as Severity })}
                  options={["low", "medium", "high", "critical"].map((s) => ({ value: s, label: s }))}
                />
              </Field>
              <Field label="Rule groups (optional)">
                <TagInput value={trigger.rule_groups ?? []} disabled={!editable} onChange={(v) => setTrigger({ ...trigger, rule_groups: v })} placeholder="authentication_failed…" />
              </Field>
            </>
          )}
          {trigger.type === "schedule" && (
            <Field label="Cron expression" hint="UTC, e.g. 0 */6 * * *">
              <input className="input font-mono" disabled={!editable} value={trigger.cron ?? ""} onChange={(e) => setTrigger({ ...trigger, cron: e.target.value })} />
            </Field>
          )}
        </div>
        {editable && dirty && (
          <div className="mt-4 flex justify-end">
            <button
              className="btn-primary"
              disabled={save.isPending}
              onClick={() =>
                save.mutate({ id: wf.id, body: { enabled, trigger } }, { onSuccess: () => toast.success("Workflow saved"), onError: (e) => toast.error("Save failed", errorMessage(e)) })
              }
            >
              {save.isPending ? <Spinner className="text-black" /> : <Save className="h-4 w-4" />} Save
            </button>
          </div>
        )}
      </Card>
      <Card>
        <CardHeader title="Recent runs" />
        <div className="pt-2">
          <Async q={runs}>{(d) => <RunsTable runs={d.items} />}</Async>
        </div>
      </Card>
      <RunModal wf={wf} open={runOpen} onClose={() => setRunOpen(false)} />
    </div>
  );
}

function RunModal({ wf, open, onClose }: { wf: Workflow; open: boolean; onClose: () => void }) {
  const run = useRunWorkflow();
  const toast = useToast();
  const navigate = useNavigate();
  const sample =
    wf.trigger.type === "alert"
      ? { alert_id: "", note: "Leave alert_id empty to let the entry agent pull the latest high-severity alerts from Wazuh." }
      : wf.trigger.type === "schedule"
        ? { scope: "all-agents", lookback: "24h" }
        : { case_id: "", instructions: "" };
  const [text, setText] = useState(JSON.stringify(sample, null, 2));
  let parsed: Record<string, unknown> | null = null;
  try {
    const v = JSON.parse(text) as unknown;
    parsed = v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
  } catch {
    parsed = null;
  }
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Run ${wf.name}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={!parsed || run.isPending}
            onClick={() =>
              parsed &&
              run.mutate(
                { id: wf.id, input: parsed },
                {
                  onSuccess: (r) => {
                    toast.success("Run started", wf.name);
                    onClose();
                    navigate(`/runs/${r.id}`);
                  },
                  onError: (e) => toast.error("Couldn't start run", errorMessage(e)),
                },
              )
            }
          >
            {run.isPending ? <Spinner className="text-black" /> : <Play className="h-4 w-4" />} Start run
          </button>
        </>
      }
    >
      <Field label="Input (JSON)" hint={parsed ? "Passed to the entry agent." : "Invalid JSON object."}>
        <textarea className={cn("textarea min-h-[180px] font-mono text-[12.5px]", !parsed && "border-danger/50")} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
    </Modal>
  );
}
