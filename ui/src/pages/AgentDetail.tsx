import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Save } from "lucide-react";
import { useAgent, useAgentPrompt, useAgents, useProviders, useSkills, useUpdateAgent } from "@/api/hooks";
import type { AgentDetail as AgentT, AutonomyLevel } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Badge, Card, CardHeader, ErrorState, Field, Kv, Markdown, ScoreRing, Select, SkeletonRows, Spinner, StatusDot, Tabs, Toggle } from "@/components/ui";
import { AgentAvatar } from "@/components/icons";
import { RunsTable } from "@/components/RunsTable";
import { SeriesChart, useColors } from "@/components/charts";
import { fmtMs, fmtNum, fmtPct, fmtUsd, relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { AUTONOMY_LEVELS, FALLBACK_PROVIDERS } from "@/lib/providers";
import { cn } from "@/lib/cn";

type Tab = "profile" | "health" | "runs" | "config" | "prompt";

export default function AgentDetail() {
  const { id = "" } = useParams();
  const q = useAgent(id);
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("profile");
  if (q.isLoading) return <SkeletonRows rows={10} />;
  if (q.error || !q.data) return <ErrorState error={q.error ?? "Not found"} onRetry={() => q.refetch()} />;
  const a = q.data;

  return (
    <div>
      <div className="border-b border-line px-4 py-4 md:px-6">
        <Link to="/agents" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
          <ArrowLeft className="h-3.5 w-3.5" /> Agent roster
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <AgentAvatar icon={a.icon} color={a.avatar_color} size="lg" running={a.status === "running"} />
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-normal tracking-tight">{a.name}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
              <span style={{ color: a.avatar_color }}>{a.codename}</span>·<span className="uppercase">{a.tier}</span>·<span className="capitalize">{a.category}</span>·
              <span className="flex items-center gap-1.5">
                <StatusDot value={a.enabled ? a.status : "disabled"} pulse={a.status === "running"} />
                {a.enabled ? a.status : "disabled"}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <ScoreRing score={a.health.score} size={52} />
            <div className="text-xs text-muted">
              <div className="text-sm capitalize text-fg">{a.health.status}</div>
              health score
            </div>
          </div>
        </div>
      </div>
      <div className="px-4 md:px-6">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "profile", label: "Profile" },
            { value: "health", label: "Health & metrics" },
            { value: "runs", label: "Recent runs", count: a.recent_runs.length },
            ...(can("agents:read") ? [{ value: "config" as Tab, label: "Configuration" }] : []),
            ...(can("runs:debug") ? [{ value: "prompt" as Tab, label: "Prompt & tools" }] : []),
          ]}
        />
      </div>
      <div className="p-4 md:p-6">
        {tab === "profile" && <Profile a={a} />}
        {tab === "health" && <HealthTab a={a} />}
        {tab === "runs" && (
          <Card>
            <RunsTable runs={a.recent_runs} />
          </Card>
        )}
        {tab === "config" && <Config a={a} />}
        {tab === "prompt" && <PromptTab id={a.id} />}
      </div>
    </div>
  );
}

function Profile({ a }: { a: AgentT }) {
  const agents = useAgents();
  const byId = new Map((agents.data ?? []).map((x) => [x.id, x]));
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <Card>
          <CardHeader title="Persona" />
          <div className="px-5 pb-5 pt-2">
            <Markdown>{a.persona}</Markdown>
            {a.responsibilities.length > 0 && (
              <>
                <div className="label mt-4">Responsibilities</div>
                <ul className="space-y-1.5">
                  {a.responsibilities.map((r) => (
                    <li key={r} className="flex gap-2 text-sm">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                      {r}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Skills" subtitle="Loaded on demand through the Strands AgentSkills plugin" right={<Link to="/skills" className="text-xs text-accent hover:underline">Library</Link>} />
          <div className="flex flex-wrap gap-2 p-5 pt-3">
            {a.skills.map((s) => (
              <Link key={s.id} to={`/skills?open=${s.id}`} className="rounded-lg border border-line bg-card2/50 px-2.5 py-1.5 text-sm hover:border-accent/40">
                {s.name}
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Tools" subtitle={`${a.tools.length} available. State-changing Wazuh tools are never exposed to agents.`} />
          <div className="grid gap-x-6 px-5 pb-4 pt-2 md:grid-cols-2">
            {a.tools.map((t) => (
              <div key={t.name} className="flex items-center justify-between border-b border-line/60 py-2 text-sm">
                <span className="truncate font-mono text-[12.5px]">{t.name}</span>
                <span className="flex gap-1.5">
                  <Badge tone={t.source === "mcp" ? "info" : "neutral"}>{t.source}</Badge>
                  <Badge tone={t.access === "verify" ? "success" : t.access === "platform" ? "accent" : "neutral"}>{t.access}</Badge>
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <div className="space-y-4">
        <Card>
          <CardHeader title="Standards" />
          <div className="flex flex-wrap gap-1.5 p-5 pt-3">
            {a.standards.map((s) => (
              <Link key={s.id} to={`/standards?open=${s.id}`} className="rounded-md border border-info/25 bg-info/5 px-2 py-1 text-xs text-info hover:border-info/50">
                {s.name}
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Handoffs" subtitle="Agents this one can hand work to in a swarm" />
          <div className="p-5 pt-3">
            <div className="flex items-center gap-3">
              <AgentAvatar icon={a.icon} color={a.avatar_color} size="sm" />
              <span className="text-sm">{a.codename}</span>
            </div>
            <div className="ml-3 mt-2 space-y-2 border-l border-dashed border-line pl-5">
              {a.handoffs.map((h) => {
                const t = byId.get(h);
                return (
                  <Link key={h} to={`/agents/${h}`} className="flex items-center gap-2 text-sm hover:text-accent">
                    <ArrowRight className="h-3.5 w-3.5 text-subtle" />
                    {t && <AgentAvatar icon={t.icon} color={t.avatar_color} size="sm" />}
                    <span>{t?.name ?? h}</span>
                  </Link>
                );
              })}
              {!a.handoffs.length && <p className="text-sm text-muted">Terminal agent, no handoffs.</p>}
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Runtime" />
          <div className="px-5 pb-4 pt-2">
            <Kv k="Model" v={<span className="font-mono text-xs">{a.model.provider} · {a.model.model_id}</span>} />
            <Kv k="Model source" v={a.model.inherited ? "Platform default" : "Agent override"} />
            <Kv k="Autonomy cap" v={<span className="capitalize">{a.autonomy_cap}</span>} />
            <Kv k="Last run" v={relTime(a.health.last_run_at)} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function HealthTab({ a }: { a: AgentT }) {
  const col = useColors();
  const h = a.health;
  const stats = [
    { k: "Runs (24h)", v: fmtNum(h.runs_24h) },
    { k: "Error rate", v: fmtPct(h.error_rate, 1, true) },
    { k: "Avg latency", v: fmtMs(h.avg_latency_ms) },
    { k: "p95 latency", v: fmtMs(h.p95_latency_ms) },
    { k: "Tokens (24h)", v: fmtNum(h.tokens_24h) },
    { k: "Cost (24h)", v: fmtUsd(h.cost_24h_usd) },
  ];
  const pts = (key: "runs" | "errors" | "avg_latency_ms" | "tokens") => a.metrics_7d.map((m) => ({ ts: m.day, value: m[key] }));
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {stats.map((s) => (
          <Card key={s.k} className="p-4">
            <div className="text-xs text-muted">{s.k}</div>
            <div className="mt-1 text-xl">{s.v}</div>
          </Card>
        ))}
      </div>
      {h.last_error && (
        <Card className="border-danger/30 p-4">
          <div className="text-xs text-danger">Last error</div>
          <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-fg/80">{h.last_error}</pre>
        </Card>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Runs and errors (7d)" />
          <div className="p-3">
            <SeriesChart series={[{ key: "runs", label: "Runs", color: col.accent, points: pts("runs") }, { key: "errors", label: "Errors", color: col.danger, points: pts("errors") }]} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Latency and tokens (7d)" />
          <div className="p-3">
            <SeriesChart series={[{ key: "lat", label: "Avg latency (ms)", color: col.info, points: pts("avg_latency_ms") }]} valueFormatter={(v) => fmtMs(v)} height={105} />
            <SeriesChart series={[{ key: "tok", label: "Tokens", color: col.success, points: pts("tokens") }]} height={105} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function Config({ a }: { a: AgentT }) {
  const { can } = useAuth();
  const editable = can("agents:write");
  const upd = useUpdateAgent(a.id);
  const skills = useSkills();
  const providers = useProviders();
  const toast = useToast();
  const [enabled, setEnabled] = useState(a.enabled);
  const [override, setOverride] = useState(!a.model.inherited);
  const [provider, setProvider] = useState(a.model.provider);
  const [modelId, setModelId] = useState(a.model.model_id);
  const [cap, setCap] = useState<AutonomyLevel>(a.autonomy_cap);
  const [sel, setSel] = useState<string[]>(a.skills.map((s) => s.id));
  const [extra, setExtra] = useState("");

  useEffect(() => {
    setEnabled(a.enabled);
    setOverride(!a.model.inherited);
    setProvider(a.model.provider);
    setModelId(a.model.model_id);
    setCap(a.autonomy_cap);
    setSel(a.skills.map((s) => s.id));
  }, [a]);

  const plist = providers.data?.length ? providers.data : FALLBACK_PROVIDERS;
  const save = () =>
    upd.mutate(
      {
        enabled,
        autonomy_cap: cap,
        skills: sel,
        model_override: override ? { provider, model_id: modelId } : null,
        ...(extra.trim() ? { system_prompt_extra: extra.trim() } : {}),
      },
      { onSuccess: () => toast.success("Agent updated", a.name), onError: (e) => toast.error("Save failed", errorMessage(e)) },
    );

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="space-y-5 p-5">
        <Toggle checked={enabled} onChange={setEnabled} disabled={!editable} label={enabled ? "Agent enabled" : "Agent disabled"} />
        <div>
          <Toggle checked={override} onChange={setOverride} disabled={!editable} label="Override platform model" />
          {override && (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Provider">
                <Select value={provider} disabled={!editable} onChange={setProvider} options={plist.map((p) => ({ value: p.id, label: p.label }))} />
              </Field>
              <Field label="Model ID">
                <input className="input font-mono text-[13px]" disabled={!editable} value={modelId} onChange={(e) => setModelId(e.target.value)} />
              </Field>
            </div>
          )}
        </div>
        <Field label="Autonomy cap" hint="The most this agent may do, even if the platform policy allows more.">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {AUTONOMY_LEVELS.map((l) => (
              <button
                key={l.id}
                disabled={!editable}
                onClick={() => setCap(l.id)}
                className={cn("rounded-lg border px-2 py-2 text-sm", cap === l.id ? "border-accent/60 bg-accent/10 text-accent" : "border-line text-muted hover:text-fg")}
              >
                {l.label}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Additional instructions" hint="Appended to the system prompt, e.g. environment-specific context.">
          <textarea className="textarea font-mono text-[12.5px]" rows={5} disabled={!editable} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="e.g. Hosts in 10.20.0.0/16 are the PCI cardholder environment." />
        </Field>
      </Card>
      <Card className="p-5">
        <div className="label">Skills ({sel.length} selected)</div>
        <div className="scrollbar-thin max-h-[420px] space-y-1 overflow-y-auto pr-1">
          {(skills.data ?? []).map((s) => {
            const on = sel.includes(s.id);
            return (
              <label key={s.id} className={cn("flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2", on ? "border-accent/40 bg-accent/5" : "border-line hover:border-subtle/50")}>
                <input
                  type="checkbox"
                  className="mt-1 accent-[rgb(var(--accent))]"
                  disabled={!editable}
                  checked={on}
                  onChange={() => setSel(on ? sel.filter((x) => x !== s.id) : [...sel, s.id])}
                />
                <span className="min-w-0">
                  <span className="block text-sm">{s.name}</span>
                  <span className="block text-xs text-muted">{s.description}</span>
                </span>
              </label>
            );
          })}
          {skills.isLoading && <Spinner />}
        </div>
        {editable && (
          <div className="mt-5 flex justify-end">
            <button className="btn-primary" onClick={save} disabled={upd.isPending}>
              {upd.isPending ? <Spinner className="text-black" /> : <Save className="h-4 w-4" />} Save changes
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}

function PromptTab({ id }: { id: string }) {
  const q = useAgentPrompt(id);
  if (q.isLoading) return <SkeletonRows />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const p = q.data;
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card>
        <CardHeader title="Composed system prompt" subtitle={`${p.system_prompt.length.toLocaleString()} characters`} />
        <pre className="scrollbar-thin m-4 max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-deep p-4 font-mono text-[12px] leading-relaxed text-fg/85">
          {p.system_prompt}
        </pre>
      </Card>
      <div className="space-y-4">
        <Card>
          <CardHeader title="Skills injected" />
          <div className="flex flex-wrap gap-1.5 p-5 pt-3">
            {p.skills_injected.map((s) => (
              <span key={s} className="chip">
                {s}
              </span>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Tool specs" subtitle={`${p.tools.length} tools sent to the model`} />
          <div className="scrollbar-thin max-h-[50vh] overflow-y-auto px-5 pb-4 pt-2">
            {p.tools.map((t) => (
              <div key={t.name} className="border-b border-line/60 py-2 last:border-0">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[12.5px]">{t.name}</span>
                  <Badge tone={t.source === "mcp" ? "info" : "neutral"}>{t.source}</Badge>
                </div>
                <div className="mt-0.5 line-clamp-2 text-xs text-muted">{t.description}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
