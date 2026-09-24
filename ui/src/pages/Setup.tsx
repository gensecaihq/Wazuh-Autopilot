import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Check, CheckCircle2, ChevronLeft, ChevronRight, CircleX, Cpu, Loader2, Plug, Server } from "lucide-react";
import { api, errorMessage } from "@/api/client";
import type { AutonomyLevel, ModelSettings, ModelTestResult, ProviderInfo, WazuhTestResult } from "@/api/types";
import { Logo } from "@/components/Layout";
import { Field } from "@/components/ui";
import { AUTONOMY_LEVELS, FALLBACK_PROVIDERS } from "@/lib/providers";
import { cn } from "@/lib/cn";
import { useToast } from "@/lib/toast";
import { ModelFields } from "./settings/ModelFields";

const STEPS = ["Organization", "Administrator", "Wazuh MCP", "Model", "Autonomy", "Review"];

const DEFAULT_MODEL: ModelSettings = {
  provider: "bedrock",
  model_id: "global.anthropic.claude-sonnet-5",
  base_url: "",
  api_key: "",
  region: "us-east-1",
  temperature: 0.2,
  max_tokens: 4096,
  guardrail_id: "",
  guardrail_version: "DRAFT",
  price_in_per_mtok: 3,
  price_out_per_mtok: 15,
};

export default function Setup() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [org, setOrg] = useState("");
  const [admin, setAdmin] = useState({ name: "", email: "", password: "", confirm: "" });
  const [wazuh, setWazuh] = useState({ mcp_url: "http://wazuh-mcp:3000", api_key: "" });
  const [model, setModel] = useState<ModelSettings>(DEFAULT_MODEL);
  const [autonomy, setAutonomy] = useState<AutonomyLevel>("recommend");
  const [providers, setProviders] = useState<ProviderInfo[]>(FALLBACK_PROVIDERS);
  const [wTest, setWTest] = useState<WazuhTestResult | null>(null);
  const [mTest, setMTest] = useState<ModelTestResult | null>(null);
  const [testing, setTesting] = useState<"w" | "m" | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.public
      .get<ProviderInfo[] | { items: ProviderInfo[] }>("/settings/providers")
      .then((r) => {
        const list = Array.isArray(r) ? r : r.items;
        if (list?.length) setProviders(list);
      })
      .catch(() => {});
  }, []);

  const valid = [
    org.trim().length > 1,
    admin.name.trim() && /\S+@\S+\.\S+/.test(admin.email) && admin.password.length >= 10 && admin.password === admin.confirm,
    wazuh.mcp_url.trim().length > 0,
    !!model.provider,
    true,
    true,
  ];

  const testWazuh = async () => {
    setTesting("w");
    setWTest(null);
    try {
      setWTest(await api.public.post<WazuhTestResult>("/settings/test/wazuh", wazuh));
    } catch (e) {
      setWTest({ ok: false, latency_ms: 0, tools_total: 0, tools_read: 0, tools_write: 0, write_scope: false, version: "", error: errorMessage(e) });
    } finally {
      setTesting(null);
    }
  };
  const testModel = async () => {
    setTesting("m");
    setMTest(null);
    try {
      setMTest(await api.public.post<ModelTestResult>("/settings/test/model", model));
    } catch (e) {
      setMTest({ ok: false, latency_ms: 0, provider: model.provider, model_id: model.model_id, sample: "", error: errorMessage(e) });
    } finally {
      setTesting(null);
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      await api.public.post("/setup/complete", {
        org_name: org.trim(),
        admin_email: admin.email.trim(),
        admin_name: admin.name.trim(),
        admin_password: admin.password,
        wazuh,
        model,
        autonomy_level: autonomy,
      });
      await qc.invalidateQueries({ queryKey: ["setup"] });
      toast.success("Setup complete", "Sign in with your administrator account.");
      navigate("/login", { replace: true });
    } catch (e) {
      toast.error("Setup failed", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-full bg-bg">
      <div className="absolute inset-x-0 top-0 h-80" style={{ background: "radial-gradient(ellipse 50% 100% at 50% 0%, rgb(var(--glow) / .10), transparent)" }} />
      <div className="relative mx-auto max-w-3xl px-4 py-10">
        <div className="flex items-center justify-between">
          <Logo />
          <span className="text-xs text-muted">First-run configuration</span>
        </div>

        <ol className="mt-10 flex items-center gap-2 overflow-x-auto">
          {STEPS.map((s, i) => (
            <li key={s} className="flex items-center gap-2">
              <button
                onClick={() => i < step && setStep(i)}
                className={cn(
                  "flex items-center gap-2 whitespace-nowrap rounded-full border px-3 py-1 text-xs",
                  i === step ? "border-accent/50 bg-accent/10 text-accent" : i < step ? "border-line bg-card2 text-fg" : "border-line text-subtle",
                )}
              >
                <span className={cn("flex h-4 w-4 items-center justify-center rounded-full text-[10px]", i < step ? "bg-success text-black" : "bg-line")}>
                  {i < step ? <Check className="h-3 w-3" /> : i + 1}
                </span>
                {s}
              </button>
              {i < STEPS.length - 1 && <span className="h-px w-4 bg-line" />}
            </li>
          ))}
        </ol>

        <div className="card mt-6 p-6">
          {step === 0 && (
            <div className="space-y-4">
              <StepTitle title="Your organization" body="Shown in reports and the header." />
              <Field label="Organization name">
                <input className="input" value={org} onChange={(e) => setOrg(e.target.value)} placeholder="Acme Corp" autoFocus />
              </Field>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <StepTitle title="Administrator account" body="This account holds the Administrator role. You can invite more users later." />
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Full name">
                  <input className="input" value={admin.name} onChange={(e) => setAdmin({ ...admin, name: e.target.value })} />
                </Field>
                <Field label="Email">
                  <input className="input" type="email" value={admin.email} onChange={(e) => setAdmin({ ...admin, email: e.target.value })} />
                </Field>
                <Field label="Password" hint="At least 10 characters.">
                  <input className="input" type="password" value={admin.password} onChange={(e) => setAdmin({ ...admin, password: e.target.value })} />
                </Field>
                <Field label="Confirm password" hint={admin.confirm && admin.confirm !== admin.password ? "Passwords don't match." : undefined}>
                  <input className="input" type="password" value={admin.confirm} onChange={(e) => setAdmin({ ...admin, confirm: e.target.value })} />
                </Field>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <StepTitle
                title="Connect the Wazuh MCP Server"
                body="Agents reach Wazuh through gensecaihq/Wazuh-MCP-Server over Streamable HTTP. The API key is exchanged for a JWT at /auth/token."
              />
              <Field label="MCP server base URL" hint="Without /mcp, e.g. https://wazuh-mcp.internal:3000">
                <input className="input font-mono" value={wazuh.mcp_url} onChange={(e) => setWazuh({ ...wazuh, mcp_url: e.target.value })} />
              </Field>
              <Field label="MCP API key" hint="Response actions need a key with the wazuh:write scope (MCP_API_KEY_SCOPES=wazuh:read wazuh:write).">
                <input className="input font-mono" type="password" value={wazuh.api_key} onChange={(e) => setWazuh({ ...wazuh, api_key: e.target.value })} placeholder="wazuh_…" />
              </Field>
              <div className="flex items-center gap-3">
                <button className="btn-secondary" onClick={testWazuh} disabled={testing === "w"}>
                  {testing === "w" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
                  Test connection
                </button>
                <span className="text-xs text-subtle">Optional. You can finish setup and connect later.</span>
              </div>
              {wTest && <WazuhResult r={wTest} />}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <StepTitle title="Model provider" body="Every agent uses this unless it has an override. You can change it any time in Settings → Models." />
              <div className="grid gap-2 sm:grid-cols-2">
                {providers.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setModel({ ...model, provider: p.id, ...p.defaults })}
                    className={cn(
                      "rounded-xl border p-3 text-left transition",
                      model.provider === p.id ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30" : "border-line bg-card2/40 hover:border-subtle/60",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {p.local ? <Server className="h-4 w-4 text-info" /> : <Cpu className="h-4 w-4 text-accent" />}
                      <span className="text-sm">{p.label}</span>
                      {p.local && <span className="chip ml-auto">self-hosted</span>}
                    </div>
                    <p className="mt-1 text-xs text-muted">{p.description}</p>
                  </button>
                ))}
              </div>
              <ModelFields value={model} onChange={setModel} provider={providers.find((p) => p.id === model.provider)} />
              <div className="flex items-center gap-3">
                <button className="btn-secondary" onClick={testModel} disabled={testing === "m"}>
                  {testing === "m" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cpu className="h-4 w-4" />}
                  Test model
                </button>
              </div>
              {mTest && <ModelResult r={mTest} />}
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <StepTitle title="Autonomy level" body="How far agents may go without a human. Per-action rules and protected targets are configured under Governance." />
              <AutonomyPicker value={autonomy} onChange={setAutonomy} />
            </div>
          )}

          {step === 5 && (
            <div className="space-y-3">
              <StepTitle title="Review" body="Confirm and create your workspace." />
              <ReviewRow k="Organization" v={org} />
              <ReviewRow k="Administrator" v={`${admin.name} · ${admin.email}`} />
              <ReviewRow k="Wazuh MCP" v={wazuh.mcp_url + (wTest ? (wTest.ok ? " · connected" : " · not verified") : "")} />
              <ReviewRow k="Model" v={`${providers.find((p) => p.id === model.provider)?.label ?? model.provider} · ${model.model_id || "default"}`} />
              <ReviewRow k="Autonomy" v={AUTONOMY_LEVELS.find((a) => a.id === autonomy)?.label ?? autonomy} />
            </div>
          )}

          <div className="mt-8 flex items-center justify-between border-t border-line pt-4">
            <button className="btn-ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
              <ChevronLeft className="h-4 w-4" /> Back
            </button>
            {step < STEPS.length - 1 ? (
              <button className="btn-primary" disabled={!valid[step]} onClick={() => setStep(step + 1)}>
                Continue <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button className="btn-primary" disabled={busy} onClick={finish}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create workspace
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StepTitle({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h2 className="text-lg font-normal">{title}</h2>
      <p className="mt-0.5 text-sm text-muted">{body}</p>
    </div>
  );
}

function ReviewRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 rounded-lg border border-line bg-card2/40 px-3 py-2.5 text-sm">
      <span className="text-muted">{k}</span>
      <span className="text-right">{v}</span>
    </div>
  );
}

export function WazuhResult({ r }: { r: WazuhTestResult }) {
  return (
    <div className={cn("rounded-lg border p-3 text-sm", r.ok ? "border-success/30 bg-success/5" : "border-danger/30 bg-danger/5")}>
      <div className="flex items-center gap-2">
        {r.ok ? <CheckCircle2 className="h-4 w-4 text-success" /> : <CircleX className="h-4 w-4 text-danger" />}
        {r.ok ? `Connected in ${r.latency_ms}ms` : "Connection failed"}
        {r.version && <span className="chip">{r.version}</span>}
      </div>
      {r.ok ? (
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted sm:grid-cols-4">
          <span>{r.tools_total} tools</span>
          <span>{r.tools_read} read</span>
          <span>{r.tools_write} write</span>
          <span className={r.write_scope ? "text-success" : "text-warn"}>{r.write_scope ? "wazuh:write granted" : "read-only key"}</span>
        </div>
      ) : (
        <div className="mt-1 break-words text-xs text-muted">{r.error}</div>
      )}
      {r.ok && !r.write_scope && (
        <div className="mt-2 text-xs text-warn">Response actions can't execute with a read-only key. Agents can still triage and propose actions.</div>
      )}
    </div>
  );
}

export function ModelResult({ r }: { r: ModelTestResult }) {
  return (
    <div className={cn("rounded-lg border p-3 text-sm", r.ok ? "border-success/30 bg-success/5" : "border-danger/30 bg-danger/5")}>
      <div className="flex items-center gap-2">
        {r.ok ? <CheckCircle2 className="h-4 w-4 text-success" /> : <CircleX className="h-4 w-4 text-danger" />}
        {r.ok ? `${r.provider} · ${r.model_id} responded in ${r.latency_ms}ms` : "Model test failed"}
      </div>
      <div className="mt-1 break-words text-xs text-muted">{r.ok ? `“${r.sample}”` : r.error}</div>
    </div>
  );
}

export function AutonomyPicker({ value, onChange, disabled }: { value: AutonomyLevel; onChange: (v: AutonomyLevel) => void; disabled?: boolean }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {AUTONOMY_LEVELS.map((a) => (
        <button
          key={a.id}
          disabled={disabled}
          onClick={() => onChange(a.id)}
          className={cn(
            "rounded-xl border p-4 text-left transition disabled:cursor-not-allowed",
            value === a.id ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30" : "border-line bg-card2/40 hover:border-subtle/60",
          )}
        >
          <div className="flex items-center gap-2">
            <span className={cn("rounded-md px-1.5 py-0.5 text-[10px] font-semibold", value === a.id ? "bg-accent text-black" : "bg-line text-muted")}>{a.tag}</span>
            <span className="text-sm">{a.label}</span>
            {a.id === "recommend" && <span className="chip ml-auto">default</span>}
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-muted">{a.desc}</p>
        </button>
      ))}
    </div>
  );
}
