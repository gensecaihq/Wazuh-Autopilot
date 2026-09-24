import { useEffect, useState } from "react";
import { Save, ShieldAlert } from "lucide-react";
import { useActionCatalog, usePolicy, useSavePolicy } from "@/api/hooks";
import type { ActionRule, Policy as PolicyT } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Badge, Card, CardHeader, ErrorState, Field, PageBody, PageHeader, riskTone, Select, SkeletonRows, Spinner, TagInput, Toggle } from "@/components/ui";
import { AutonomyPicker } from "./Setup";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";

export default function Policy() {
  const q = usePolicy();
  const catalog = useActionCatalog();
  const save = useSavePolicy();
  const { can } = useAuth();
  const toast = useToast();
  const editable = can("policy:write");
  const [p, setP] = useState<PolicyT | null>(null);
  useEffect(() => {
    if (q.data) setP(structuredClone(q.data));
  }, [q.data]);

  if (q.isLoading || (!p && !q.error)) return <SkeletonRows rows={10} />;
  if (q.error || !p) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;

  const dirty = JSON.stringify(p) !== JSON.stringify(q.data);
  const cat = new Map((catalog.data ?? []).map((c) => [c.type, c]));
  const setRule = (i: number, patch: Partial<ActionRule>) => setP({ ...p, action_rules: p.action_rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) });

  return (
    <div>
      <PageHeader
        title="Autonomy Policy"
        subtitle="Decide how far the swarm may act without a human, per action and per target"
        right={
          editable && (
            <button className="btn-primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(p, { onSuccess: () => toast.success("Policy saved"), onError: (e) => toast.error("Save failed", errorMessage(e)) })}>
              {save.isPending ? <Spinner className="text-black" /> : <Save className="h-4 w-4" />} Save policy
            </button>
          )
        }
      />
      <PageBody>
        <Card className="p-5">
          <h3 className="mb-1 text-[15px]">Platform autonomy level</h3>
          <p className="mb-4 text-sm text-muted">Agents never call Wazuh active-response tools directly. They propose; this policy decides who approves and who executes.</p>
          <AutonomyPicker value={p.autonomy_level} onChange={(v) => setP({ ...p, autonomy_level: v })} disabled={!editable} />
        </Card>

        <Card>
          <CardHeader title="Per-action rules" subtitle="Override the platform level for individual response actions" />
          <div className="scrollbar-thin overflow-x-auto p-2">
            <table className="w-full min-w-[860px]">
              <thead>
                <tr className="border-b border-line">
                  <th className="th">Action</th>
                  <th className="th">Risk</th>
                  <th className="th">Autonomy</th>
                  <th className="th w-[220px]">Min confidence</th>
                  <th className="th">Max / hour</th>
                  <th className="th">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {p.action_rules.map((r, i) => {
                  const c = cat.get(r.type);
                  return (
                    <tr key={r.type} className="border-b border-line/60 last:border-0">
                      <td className="td">
                        <div>{c?.label ?? r.type}</div>
                        <div className="text-[11px] text-subtle">
                          <span className="font-mono">{c?.mcp_tool ?? r.type}</span>
                          {c?.d3fend && <> · D3FEND {c.d3fend}</>}
                          {c && !c.reversible && <span className="text-warn"> · irreversible</span>}
                        </div>
                      </td>
                      <td className="td">{c ? <Badge tone={riskTone[c.risk] ?? "neutral"}>{c.risk}</Badge> : "—"}</td>
                      <td className="td">
                        <Select
                          className="w-40"
                          value={r.autonomy}
                          disabled={!editable}
                          onChange={(v) => setRule(i, { autonomy: v as ActionRule["autonomy"] })}
                          options={[
                            { value: "inherit", label: "Inherit platform" },
                            { value: "manual", label: "Manual (L1)" },
                            { value: "supervised", label: "Supervised (L2)" },
                            { value: "autonomous", label: "Autonomous (L3)" },
                          ]}
                        />
                      </td>
                      <td className="td">
                        <div className="flex items-center gap-3">
                          <input type="range" min={0.5} max={1} step={0.01} value={r.min_confidence} disabled={!editable} onChange={(e) => setRule(i, { min_confidence: Number(e.target.value) })} className="w-32 accent-[rgb(var(--accent))]" />
                          <span className="w-10 text-sm">{Math.round(r.min_confidence * 100)}%</span>
                        </div>
                      </td>
                      <td className="td">
                        <input className="input w-20" type="number" min={0} value={r.max_per_hour} disabled={!editable} onChange={(e) => setRule(i, { max_per_hour: Number(e.target.value) })} />
                      </td>
                      <td className="td">
                        <Toggle checked={r.enabled} disabled={!editable} onChange={(v) => setRule(i, { enabled: v })} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="space-y-4 p-5">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-accent" />
              <h3 className="text-[15px]">Protected targets</h3>
            </div>
            <p className="text-sm text-muted">Never auto-executed against, whatever the autonomy level. Actions on these always need a human.</p>
            <Field label="IP addresses / CIDRs">
              <TagInput value={p.protected_targets.ips} disabled={!editable} onChange={(v) => setP({ ...p, protected_targets: { ...p.protected_targets, ips: v } })} placeholder="10.0.0.1, 10.10.0.0/16" />
            </Field>
            <Field label="Hostnames">
              <TagInput value={p.protected_targets.hosts} disabled={!editable} onChange={(v) => setP({ ...p, protected_targets: { ...p.protected_targets, hosts: v } })} placeholder="dc01, wazuh-manager" />
            </Field>
            <Field label="Users">
              <TagInput value={p.protected_targets.users} disabled={!editable} onChange={(v) => setP({ ...p, protected_targets: { ...p.protected_targets, users: v } })} placeholder="root, Administrator" />
            </Field>
            <Field label="Wazuh agent IDs">
              <TagInput value={p.protected_targets.agent_ids} disabled={!editable} onChange={(v) => setP({ ...p, protected_targets: { ...p.protected_targets, agent_ids: v } })} placeholder="000" />
            </Field>
          </Card>
          <Card className="space-y-5 p-5">
            <h3 className="text-[15px]">Approval controls</h3>
            <Field label="Approval expiry (minutes)" hint="Proposed actions expire if nobody approves them in time.">
              <input className="input w-32" type="number" min={5} value={p.approval_expiry_minutes} disabled={!editable} onChange={(e) => setP({ ...p, approval_expiry_minutes: Number(e.target.value) })} />
            </Field>
            <Toggle checked={p.require_two_person} disabled={!editable} onChange={(v) => setP({ ...p, require_two_person: v })} label="Two-person rule: the approver can't also execute" />
            <Toggle checked={p.business_hours_only} disabled={!editable} onChange={(v) => setP({ ...p, business_hours_only: v })} label="Autonomous execution only during business hours" />
          </Card>
        </div>
      </PageBody>
    </div>
  );
}
