import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Bot, Loader2, ShieldCheck, Workflow } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useSetupStatus } from "@/api/hooks";
import { errorMessage } from "@/api/client";
import { Logo } from "@/components/Layout";

export default function Login() {
  const { token, login } = useAuth();
  const setup = useSetupStatus();
  const navigate = useNavigate();
  const loc = useLocation();
  const demo = setup.data?.demo_mode;
  const [email, setEmail] = useState(demo ? "admin@autopilot.local" : "");
  const [password, setPassword] = useState(demo ? "Autopilot!2026" : "");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const from = (loc.state as { from?: string } | null)?.from || "/";
  if (token) return <Navigate to={from} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (ex) {
      setErr(errorMessage(ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-full bg-bg lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden border-r border-line bg-deep lg:block">
        <div className="absolute inset-0" style={{ background: "radial-gradient(ellipse 70% 55% at 35% 60%, rgb(var(--glow) / .16), transparent 70%)" }} />
        <div
          className="absolute inset-0 opacity-[0.18]"
          style={{ backgroundImage: "radial-gradient(rgb(var(--muted)) 1px, transparent 1px)", backgroundSize: "22px 22px" }}
        />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Logo />
          <div className="max-w-md">
            <h1 className="text-4xl font-light leading-tight tracking-tight">
              An agent swarm that runs your <span className="text-accent">Wazuh</span> SOC.
            </h1>
            <p className="mt-4 text-muted">
              Specialist AI agents triage, investigate and contain threats through the Wazuh MCP server, grounded in NIST, MITRE ATT&CK and CIS, with
              the human approvals your governance model requires.
            </p>
            <div className="mt-8 space-y-3">
              {[
                { icon: Bot, t: "13 specialist agents with Wazuh skills", d: "Built on Strands Agents: swarm handoffs, graphs and evals" },
                { icon: ShieldCheck, t: "Governed autonomy", d: "From observe-only to autonomous containment, per action" },
                { icon: Workflow, t: "Full observability", d: "Every model call, tool call and handoff traced" },
              ].map((f) => (
                <div key={f.t} className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg border border-accent/25 bg-accent/10 text-accent">
                    <f.icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm">{f.t}</div>
                    <div className="text-xs text-muted">{f.d}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="text-xs text-subtle">Wazuh Autopilot · Strands edition {setup.data?.version ? `v${setup.data.version}` : ""}</div>
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          <h2 className="text-2xl font-normal tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-muted">Use your Autopilot account.</p>
          {demo && (
            <div className="mt-5 rounded-lg border border-info/30 bg-info/10 px-3 py-2 text-xs text-info">
              Demo mode: <span className="font-mono">admin@autopilot.local</span> / <span className="font-mono">Autopilot!2026</span>
            </div>
          )}
          <div className="mt-6 space-y-4">
            <div>
              <label className="label" htmlFor="email">
                Email
              </label>
              <input id="email" className="input h-10" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                className="input h-10"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {err && <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{err}</div>}
            <button className="btn-primary h-10 w-full" disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
