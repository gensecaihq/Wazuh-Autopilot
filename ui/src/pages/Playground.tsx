import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, ExternalLink, FlaskConical, Loader2, RotateCcw, Send, TerminalSquare, User as UserIcon, Wrench } from "lucide-react";
import { useAgents } from "@/api/hooks";
import { api, errorMessage } from "@/api/client";
import type { PlaygroundMessage, PlaygroundSession, SseEvent } from "@/api/types";
import { Card, EmptyState, JsonView, Markdown, PageHeader, Select, Toggle } from "@/components/ui";
import { AgentAvatar } from "@/components/icons";
import { useEvents } from "@/lib/events";
import { useToast } from "@/lib/toast";
import { fmtMs } from "@/lib/format";
import { cn } from "@/lib/cn";

const SUGGESTIONS = [
  "Pull the last 20 level 10+ alerts and triage them.",
  "Which agents are disconnected, and is that suspicious?",
  "Investigate failed SSH logins on web-prod-01 in the last 24h.",
  "Propose containment for brute force from 203.0.113.45.",
];

export default function Playground() {
  const agents = useAgents();
  const { subscribe } = useEvents();
  const toast = useToast();
  const [agentId, setAgentId] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [session, setSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [steps, setSteps] = useState<SseEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const runRef = useRef<string | null>(null);

  useEffect(() => {
    if (!agentId && agents.data?.length) setAgentId(agents.data.find((a) => a.category === "command")?.id ?? agents.data[0].id);
  }, [agents.data, agentId]);

  useEffect(() => {
    runRef.current = runId;
  }, [runId]);

  useEffect(
    () =>
      subscribe((e) => {
        const rid = typeof e.data.run_id === "string" ? e.data.run_id : null;
        if (!rid || rid !== runRef.current) return;
        if (e.type === "run.step") setSteps((s) => [...s, e]);
        if (e.type === "run.finished") {
          const out = typeof e.data.output_md === "string" ? e.data.output_md : "";
          const status = typeof e.data.status === "string" ? e.data.status : "completed";
          setMessages((m) => [...m, { role: "assistant", content: out || (status === "failed" ? `Run failed: ${String(e.data.error ?? "unknown error")}` : "(no output)"), ts: new Date().toISOString() }]);
          setSteps((s) => [...s, e]);
          setBusy(false);
        }
      }),
    [subscribe],
  );

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, busy]);

  // Fallback if SSE is unavailable: poll the session while busy.
  useEffect(() => {
    if (!busy || !session) return;
    const t = window.setInterval(async () => {
      try {
        const s = await api.get<PlaygroundSession>(`/playground/sessions/${session}`);
        const last = s.messages[s.messages.length - 1];
        if (last && last.role === "assistant" && s.messages.length > messages.length) {
          setMessages(s.messages);
          setBusy(false);
        }
      } catch {
        /* ignore */
      }
    }, 4000);
    return () => clearInterval(t);
  }, [busy, session, messages.length]);

  const reset = () => {
    setSession(null);
    setMessages([]);
    setSteps([]);
    setRunId(null);
    setBusy(false);
  };

  const send = async (text: string) => {
    if (!text.trim() || !agentId) return;
    setInput("");
    setBusy(true);
    setSteps([]);
    setMessages((m) => [...m, { role: "user", content: text.trim(), ts: new Date().toISOString() }]);
    try {
      let sid = session;
      if (!sid) {
        const s = await api.post<{ session_id: string }>("/playground/sessions", { agent_id: agentId, dry_run: dryRun });
        sid = s.session_id;
        setSession(sid);
      }
      const r = await api.post<{ run_id: string }>(`/playground/sessions/${sid}/messages`, { content: text.trim() });
      setRunId(r.run_id);
    } catch (e) {
      setBusy(false);
      toast.error("Message failed", errorMessage(e));
    }
  };

  const agent = agents.data?.find((a) => a.id === agentId);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Playground"
        subtitle="Talk to a single agent and watch every model call, tool call and handoff as it happens"
        right={
          <>
            <Select
              className="w-60"
              value={agentId}
              disabled={!!session}
              onChange={setAgentId}
              options={(agents.data ?? []).map((a) => ({ value: a.id, label: `${a.codename} · ${a.name}` }))}
            />
            <Toggle checked={dryRun} onChange={setDryRun} disabled={!!session} label={<span className="flex items-center gap-1"><FlaskConical className="h-3.5 w-3.5" /> Dry run</span>} />
            <button className="btn-secondary" onClick={reset}>
              <RotateCcw className="h-4 w-4" /> New session
            </button>
          </>
        }
      />
      <div className="grid min-h-0 flex-1 gap-4 p-4 md:p-6 xl:grid-cols-[1fr_440px]">
        <Card className="flex min-h-[520px] flex-col">
          <div className="flex items-center gap-3 border-b border-line px-4 py-3">
            {agent && <AgentAvatar icon={agent.icon} color={agent.avatar_color} size="sm" running={busy} />}
            <div className="min-w-0 flex-1">
              <div className="text-sm">{agent?.name ?? "Select an agent"}</div>
              <div className="text-[11px] text-muted">
                {dryRun ? "Dry run: action tools and state-changing platform tools are stubbed" : "Live: platform tools write to real cases and proposals"}
              </div>
            </div>
            {runId && (
              <Link to={`/runs/${runId}`} className="btn-ghost btn-sm">
                Trace <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            )}
          </div>
          <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-4">
            {!messages.length && (
              <div className="py-10">
                <EmptyState icon={<TerminalSquare className="h-5 w-5" />} title="Start a conversation" body="Try one of these prompts, or write your own." />
                <div className="mx-auto grid max-w-2xl gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)} className="rounded-lg border border-line bg-card2/40 p-3 text-left text-sm text-muted hover:border-accent/40 hover:text-fg">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}>
                <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full border", m.role === "user" ? "border-line bg-card2" : "border-accent/30 bg-accent/10 text-accent")}>
                  {m.role === "user" ? <UserIcon className="h-3.5 w-3.5 text-muted" /> : m.role === "tool" ? <Wrench className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                </span>
                <div className={cn("max-w-[85%] rounded-xl border px-4 py-3", m.role === "user" ? "border-line bg-card2" : "border-line bg-deep/40")}>
                  {m.role === "user" ? <p className="whitespace-pre-wrap text-sm">{m.content}</p> : <Markdown>{m.content}</Markdown>}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2 text-sm text-muted">
                <Loader2 className="h-4 w-4 animate-spin text-accent" /> {agent?.codename ?? "Agent"} is working… {steps.length ? `(${steps.length} steps)` : ""}
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form
            className="flex items-end gap-2 border-t border-line p-3"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <textarea
              className="textarea min-h-[42px]"
              rows={2}
              placeholder="Ask the agent to investigate, hunt or explain…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
            />
            <button className="btn-primary h-[42px]" disabled={busy || !input.trim() || !agentId}>
              <Send className="h-4 w-4" />
            </button>
          </form>
        </Card>

        <Card className="flex min-h-[520px] flex-col">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="text-sm">Event stream</span>
            <span className="text-[11px] text-muted">{steps.length} events</span>
          </div>
          <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto p-3">
            {!steps.length && <p className="py-10 text-center text-sm text-muted">Model calls, tool calls and handoffs appear here live.</p>}
            {steps.map((s, i) => (
              <StepRow key={i} e={s} />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function StepRow({ e }: { e: SseEvent }) {
  const [open, setOpen] = useState(false);
  const d = e.data;
  const kind = String(d.kind ?? (e.type === "run.finished" ? "finished" : "step"));
  const tone =
    kind === "tool" ? "text-info border-info/30 bg-info/5" : kind === "model" ? "text-accent border-accent/30 bg-accent/5" : kind === "handoff" ? "text-success border-success/30 bg-success/5" : kind === "guardrail" ? "text-warn border-warn/30 bg-warn/5" : "text-muted border-line bg-card2";
  const status = typeof d.status === "string" ? d.status : null;
  return (
    <div className="rounded-lg border border-line bg-deep/40">
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(!open)}>
        <span className={cn("rounded border px-1.5 py-0.5 text-[10px] uppercase", tone)}>{kind}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-[12px]">{String(d.name ?? d.agent_id ?? e.type)}</span>
        {typeof d.duration_ms === "number" && <span className="text-[11px] text-subtle">{fmtMs(d.duration_ms)}</span>}
        {status && status !== "ok" && <span className={cn("text-[11px]", status === "error" || status === "failed" ? "text-danger" : "text-warn")}>{status}</span>}
      </button>
      {open && (
        <div className="border-t border-line p-2">
          <JsonView value={d} />
        </div>
      )}
    </div>
  );
}
