import { useEffect, useState, type ReactNode } from "react";
import { Cpu, Loader2, Plug, Save, Send, Server } from "lucide-react";
import { useProviders, useSaveSettings, useSettings } from "@/api/hooks";
import { api, errorMessage } from "@/api/client";
import type { ModelTestResult, Settings as SettingsT, WazuhTestResult } from "@/api/types";
import { Card, ErrorState, Field, PageHeader, Select, SkeletonRows, Spinner, Tabs, TagInput, Toggle } from "@/components/ui";
import { ModelFields } from "./settings/ModelFields";
import { ModelResult, WazuhResult } from "./Setup";
import { FALLBACK_PROVIDERS } from "@/lib/providers";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/cn";

type Tab = "general" | "wazuh" | "models" | "ingestion" | "notifications" | "observability" | "swarm";
const TOOLSETS = ["alerts", "agents", "vulnerabilities", "analysis", "compliance", "system", "response", "web_search"];
const NOTIFY = ["critical_case", "approval_needed", "action_failed", "action_executed", "run_failed"];

export default function Settings() {
  const q = useSettings();
  const save = useSaveSettings();
  const { can } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("general");
  const [s, setS] = useState<SettingsT | null>(null);
  useEffect(() => {
    if (q.data) setS(structuredClone(q.data));
  }, [q.data]);

  if (q.isLoading || (!s && !q.error)) return <SkeletonRows rows={10} />;
  if (q.error || !s) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const editable = can("settings:write");
  const dirty = JSON.stringify(s) !== JSON.stringify(q.data);

  const set = <K extends keyof SettingsT>(k: K, v: Partial<SettingsT[K]>) => setS({ ...s, [k]: { ...s[k], ...v } });

  const onSave = () => {
    // Only send sections that changed; masked secrets are sent back unchanged and the API ignores them.
    const diff: Partial<SettingsT> = {};
    (Object.keys(s) as (keyof SettingsT)[]).forEach((k) => {
      if (JSON.stringify(s[k]) !== JSON.stringify(q.data?.[k])) (diff as Record<string, unknown>)[k] = s[k];
    });
    save.mutate(diff, { onSuccess: () => toast.success("Settings saved"), onError: (e) => toast.error("Save failed", errorMessage(e)) });
  };

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Configure integrations, models, ingestion and swarm limits"
        right={
          editable && (
            <button className="btn-primary" disabled={!dirty || save.isPending} onClick={onSave}>
              {save.isPending ? <Spinner className="text-black" /> : <Save className="h-4 w-4" />} Save changes
            </button>
          )
        }
      />
      <div className="px-4 md:px-6">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "general", label: "General" },
            { value: "wazuh", label: "Wazuh MCP" },
            { value: "models", label: "Models" },
            { value: "ingestion", label: "Ingestion" },
            { value: "notifications", label: "Notifications" },
            { value: "observability", label: "Observability" },
            { value: "swarm", label: "Swarm limits" },
          ]}
        />
      </div>
      <div className="max-w-4xl space-y-4 p-4 md:p-6">
        {tab === "general" && (
          <Section title="Organization">
            <Field label="Organization name">
              <input className="input" disabled={!editable} value={s.org.name} onChange={(e) => set("org", { name: e.target.value })} />
            </Field>
            <Field label="Timezone" hint="IANA name, used for reports and business-hours rules.">
              <input className="input" disabled={!editable} value={s.org.timezone} onChange={(e) => set("org", { timezone: e.target.value })} placeholder="UTC" />
            </Field>
            <Field label="Logo initials">
              <input className="input w-24" maxLength={3} disabled={!editable} value={s.org.logo_initials} onChange={(e) => set("org", { logo_initials: e.target.value })} />
            </Field>
          </Section>
        )}
        {tab === "wazuh" && <WazuhTab s={s} set={set} editable={editable} />}
        {tab === "models" && <ModelsTab s={s} set={set} editable={editable} />}
        {tab === "ingestion" && (
          <Section title="Alert ingestion" desc="Pull alerts from Wazuh through the MCP server, receive them by webhook, or both.">
            <Field label="Mode">
              <Select
                disabled={!editable}
                value={s.ingestion.mode}
                onChange={(v) => set("ingestion", { mode: v as SettingsT["ingestion"]["mode"] })}
                options={[
                  { value: "poll", label: "Poll via MCP (get_wazuh_alerts)" },
                  { value: "webhook", label: "Webhook (POST /api/v1/ingest/wazuh)" },
                  { value: "both", label: "Both" },
                ]}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Poll interval (seconds)">
                <input className="input" type="number" min={15} disabled={!editable} value={s.ingestion.poll_interval_s} onChange={(e) => set("ingestion", { poll_interval_s: Number(e.target.value) })} />
              </Field>
              <Field label="Minimum Wazuh rule level" hint="Alerts below this level are ignored.">
                <input className="input" type="number" min={0} max={15} disabled={!editable} value={s.ingestion.min_level} onChange={(e) => set("ingestion", { min_level: Number(e.target.value) })} />
              </Field>
              <Field label="Dedup window (minutes)">
                <input className="input" type="number" min={0} disabled={!editable} value={s.ingestion.dedup_window_min} onChange={(e) => set("ingestion", { dedup_window_min: Number(e.target.value) })} />
              </Field>
              <Field label="Case grouping window (minutes)" hint="Related alerts within this window join the same incident.">
                <input className="input" type="number" min={0} disabled={!editable} value={s.ingestion.group_window_min} onChange={(e) => set("ingestion", { group_window_min: Number(e.target.value) })} />
              </Field>
            </div>
            <Field label="Webhook ingest key" hint="Send as the X-Autopilot-Ingest-Key header from your Wazuh integration script.">
              <input className="input font-mono" disabled={!editable} value={s.ingestion.ingest_key} onChange={(e) => set("ingestion", { ingest_key: e.target.value })} />
            </Field>
          </Section>
        )}
        {tab === "notifications" && <NotificationsTab s={s} set={set} editable={editable} />}
        {tab === "observability" && (
          <Section title="Observability" desc="Strands emits OpenTelemetry spans for every agent, model call and tool call.">
            <Field label="OTLP endpoint" hint="e.g. http://otel-collector:4318. Leave empty to keep traces in the platform only.">
              <input className="input font-mono" disabled={!editable} value={s.observability.otlp_endpoint} onChange={(e) => set("observability", { otlp_endpoint: e.target.value })} />
            </Field>
            <Field label="OTLP headers" hint="key1=value1,key2=value2">
              <input className="input font-mono" disabled={!editable} value={s.observability.otlp_headers} onChange={(e) => set("observability", { otlp_headers: e.target.value })} />
            </Field>
            <Toggle checked={s.observability.prometheus_enabled} disabled={!editable} onChange={(v) => set("observability", { prometheus_enabled: v })} label="Expose Prometheus metrics at /metrics" />
            <Field label="Trace retention (days)">
              <input className="input w-32" type="number" min={1} disabled={!editable} value={s.observability.trace_retention_days} onChange={(e) => set("observability", { trace_retention_days: Number(e.target.value) })} />
            </Field>
          </Section>
        )}
        {tab === "swarm" && (
          <Section title="Swarm limits" desc="Guardrails on multi-agent execution (Strands Swarm / Graph settings).">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Max handoffs per run">
                <input className="input" type="number" min={1} disabled={!editable} value={s.swarm.max_handoffs} onChange={(e) => set("swarm", { max_handoffs: Number(e.target.value) })} />
              </Field>
              <Field label="Max iterations per run">
                <input className="input" type="number" min={1} disabled={!editable} value={s.swarm.max_iterations} onChange={(e) => set("swarm", { max_iterations: Number(e.target.value) })} />
              </Field>
              <Field label="Run timeout (seconds)">
                <input className="input" type="number" min={30} disabled={!editable} value={s.swarm.execution_timeout_s} onChange={(e) => set("swarm", { execution_timeout_s: Number(e.target.value) })} />
              </Field>
              <Field label="Per-agent timeout (seconds)">
                <input className="input" type="number" min={10} disabled={!editable} value={s.swarm.node_timeout_s} onChange={(e) => set("swarm", { node_timeout_s: Number(e.target.value) })} />
              </Field>
              <Field label="Max concurrent runs">
                <input className="input" type="number" min={1} disabled={!editable} value={s.swarm.max_concurrent_runs} onChange={(e) => set("swarm", { max_concurrent_runs: Number(e.target.value) })} />
              </Field>
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, desc, children }: { title: string; desc?: string; children: ReactNode }) {
  return (
    <Card className="space-y-4 p-5">
      <div>
        <h3 className="text-[15px]">{title}</h3>
        {desc && <p className="mt-0.5 text-sm text-muted">{desc}</p>}
      </div>
      {children}
    </Card>
  );
}

type SetFn = <K extends keyof SettingsT>(k: K, v: Partial<SettingsT[K]>) => void;

function WazuhTab({ s, set, editable }: { s: SettingsT; set: SetFn; editable: boolean }) {
  const [res, setRes] = useState<WazuhTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const test = async () => {
    setBusy(true);
    setRes(null);
    try {
      setRes(await api.post<WazuhTestResult>("/settings/test/wazuh", s.wazuh));
    } catch (e) {
      setRes({ ok: false, latency_ms: 0, tools_total: 0, tools_read: 0, tools_write: 0, write_scope: false, version: "", error: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Wazuh MCP Server" desc="gensecaihq/Wazuh-MCP-Server over Streamable HTTP. The API key is exchanged for a JWT at /auth/token.">
      <Field label="Base URL" hint="Without /mcp">
        <input className="input font-mono" disabled={!editable} value={s.wazuh.mcp_url} onChange={(e) => set("wazuh", { mcp_url: e.target.value })} />
      </Field>
      <Field label="API key" hint="Leave the masked value to keep the current key. Needs wazuh:write scope to execute actions.">
        <input className="input font-mono" type="password" disabled={!editable} value={s.wazuh.api_key} onChange={(e) => set("wazuh", { api_key: e.target.value })} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Request timeout (seconds)">
          <input className="input" type="number" min={5} disabled={!editable} value={s.wazuh.request_timeout_s} onChange={(e) => set("wazuh", { request_timeout_s: Number(e.target.value) })} />
        </Field>
        <div className="flex items-end pb-2">
          <Toggle checked={s.wazuh.verify_tls} disabled={!editable} onChange={(v) => set("wazuh", { verify_tls: v })} label="Verify TLS certificate" />
        </div>
      </div>
      <Field label="Toolsets exposed to agents" hint="Smaller toolsets improve tool selection on local models. State-changing response tools are never given to agents; the platform executor uses them after approval.">
        <div className="flex flex-wrap gap-2">
          {TOOLSETS.map((t) => {
            const on = s.wazuh.toolsets.includes(t);
            return (
              <button
                key={t}
                disabled={!editable}
                onClick={() => set("wazuh", { toolsets: on ? s.wazuh.toolsets.filter((x) => x !== t) : [...s.wazuh.toolsets, t] })}
                className={cn("rounded-lg border px-3 py-1.5 text-sm", on ? "border-accent/50 bg-accent/10 text-accent" : "border-line text-muted hover:text-fg")}
              >
                {t}
              </button>
            );
          })}
        </div>
      </Field>
      <div>
        <button className="btn-secondary" onClick={test} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />} Test connection
        </button>
      </div>
      {res && <WazuhResult r={res} />}
    </Section>
  );
}

function ModelsTab({ s, set, editable }: { s: SettingsT; set: SetFn; editable: boolean }) {
  const providers = useProviders();
  const list = providers.data?.length ? providers.data : FALLBACK_PROVIDERS;
  const [res, setRes] = useState<ModelTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const current = list.find((p) => p.id === s.model.provider);
  const test = async () => {
    setBusy(true);
    setRes(null);
    try {
      setRes(await api.post<ModelTestResult>("/settings/test/model", { provider: s.model.provider, model_id: s.model.model_id }));
    } catch (e) {
      setRes({ ok: false, latency_ms: 0, provider: s.model.provider, model_id: s.model.model_id, sample: "", error: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Section title="Default model provider" desc="Used by every agent without an override. Save before testing a new provider.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((p) => (
            <button
              key={p.id}
              disabled={!editable}
              onClick={() => set("model", { provider: p.id, ...p.defaults })}
              className={cn("rounded-xl border p-3 text-left transition", s.model.provider === p.id ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30" : "border-line bg-card2/40 hover:border-subtle/60")}
            >
              <div className="flex items-center gap-2">
                {p.local ? <Server className="h-4 w-4 text-info" /> : <Cpu className="h-4 w-4 text-accent" />}
                <span className="text-sm">{p.label}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-muted">{p.description}</p>
            </button>
          ))}
        </div>
      </Section>
      <Section title={`${current?.label ?? s.model.provider} configuration`}>
        <ModelFields value={s.model} onChange={(m) => set("model", m)} provider={current} disabled={!editable} showTuning />
        <div>
          <button className="btn-secondary" onClick={test} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cpu className="h-4 w-4" />} Test model
          </button>
        </div>
        {res && <ModelResult r={res} />}
      </Section>
    </>
  );
}

function NotificationsTab({ s, set, editable }: { s: SettingsT; set: SetFn; editable: boolean }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <Section title="Notifications" desc="Tell the team when something needs a human.">
      <Field label="Slack incoming webhook URL">
        <input className="input font-mono" type="password" disabled={!editable} value={s.notifications.slack_webhook_url} onChange={(e) => set("notifications", { slack_webhook_url: e.target.value })} placeholder="https://hooks.slack.com/services/…" />
      </Field>
      <Field label="Email recipients" hint="Comma-separated">
        <input className="input" disabled={!editable} value={s.notifications.email_to} onChange={(e) => set("notifications", { email_to: e.target.value })} />
      </Field>
      <Field label="Notify on">
        <TagInput
          value={s.notifications.notify_on}
          disabled={!editable}
          onChange={(v) => set("notifications", { notify_on: v })}
          placeholder={NOTIFY.filter((n) => !s.notifications.notify_on.includes(n)).join(", ")}
        />
      </Field>
      <div>
        <button
          className="btn-secondary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const r = await api.post<{ ok: boolean; error?: string }>("/settings/test/notifications");
              if (r.ok) toast.success("Test notification sent");
              else toast.error("Test failed", r.error);
            } catch (e) {
              toast.error("Test failed", errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send test
        </button>
      </div>
    </Section>
  );
}

