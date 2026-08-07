# Architecture

How Wazuh Autopilot turns a raw Wazuh alert into a governed, human-approved response. This is the map of the whole system — the agent pipeline, the runtime service, the MCP data plane, and the pluggable agent runtimes.

## The 10,000-foot view

```
   ┌────────────┐      alert webhook       ┌──────────────────────────────┐
   │   Wazuh    │ ───────────────────────▶ │   Agent Runtime (one of 3)   │
   │  Manager   │                          │  OpenClaw / Hermes / NemoClaw │
   │ + Indexer  │ ◀─── queries (MCP) ─────  │  → 7 SOC agents               │
   └────────────┘                          └───────────────┬──────────────┘
        ▲                                                   │ REST (cases, plans)
        │ active response (MCP)                             ▼
   ┌────┴───────────┐   verify / dispatch   ┌──────────────────────────────┐
   │  Wazuh MCP     │ ◀──────────────────── │      Runtime Service          │
   │  Server        │                       │  (runtime/autopilot-service)  │
   │  (48 tools)    │ ──────────────────▶   │  cases · plans · policy ·     │
   └────────────────┘     tool calls        │  approvals · KPIs · evidence  │
                                            └───────────────┬──────────────┘
                                                            │ notify / approve
                                                            ▼
                                                   ┌──────────────────┐
                                                   │  Human (Slack /  │
                                                   │  REST) — Approve │
                                                   │  + Execute       │
                                                   └──────────────────┘
```

Three planes:

- **Control plane** — the **Runtime Service** (`runtime/autopilot-service/index.js`). Owns case state, response plans, the policy engine, the two-tier approval workflow, KPIs, and evidence packs. This is the source of truth; agents and humans both act through its REST API.
- **Data plane** — the **Wazuh MCP Server** (48 tools). The only path agents use to read Wazuh (alerts, auth history, process trees, vulnerabilities) and to dispatch active response.
- **Reasoning plane** — the **agent runtime** (OpenClaw, Hermes, or NemoClaw) hosting the seven SOC agents that do the analysis.

## The SOC pipeline

Seven agents, each a security-expert persona mirroring a human SOC role, connected as a pipeline with strict handoffs. Full personas live in [`openclaw/agents/*/IDENTITY.md`](../openclaw/agents) and the team roster in [`_shared/SOUL.md`](../openclaw/agents/_shared/SOUL.md).

| # | Agent | Human role | Permission | Reads | Writes |
|---|---|---|---|---|---|
| 1 | **Triage** | Tier 1 SOC Analyst | read-only | alerts | case (auto) |
| 2 | **Correlation** | Tier 2 Analyst / Detection Engineer | read-only | cases, alerts | case links (auto) |
| 3 | **Investigation** | Tier 3 / DFIR Investigator | read-only | Wazuh Indexer (pivots) | evidence (auto) |
| 4 | **Response Planner** | Incident Response Lead | plan-only | case, evidence | plan (proposed) |
| 5 | **Policy Guard** | Security Compliance Officer | validate-only | plan, policy | decision (allow/deny) |
| 6 | **Responder** | SecOps / Containment Operator | execute (gated) | plan, approvals | active response |
| 7 | **Reporting** | SOC Manager / Metrics Analyst | read-only | metrics, cases | reports |

Agents 1–3 and 7 are **fully automated but read-only** — they can never change a host. Agents 4–6 form the response path, and nothing in that path executes without two human approvals.

### Case lifecycle

```
new ──▶ triaged ──▶ correlated ──▶ investigated ──▶ (plan proposed)
                                                          │
                                          approved ◀── PROPOSED
                                             │
                                          executed ──▶ closed   (auto-close after grace period)
                                             │
                          (also possible: false_positive at any read stage)
```

Status transitions are validated in the runtime — e.g. a plan whose actions all failed does **not** advance the case to `executed` (which would corrupt MTTR/SLA and trigger auto-close).

## Two-tier human approval

The core safety property: **AI proposes, humans dispose.**

```
Response Planner          Human (Tier 1)         Human (Tier 2)         Responder
   creates plan  ──▶  POST /plans/{id}/approve ──▶ POST /plans/{id}/execute ──▶ active response
   (state: proposed)     (authorization +           (authorization +           (verify + evidence)
                          separation of duties)      time window + rate limit)
```

Every step passes through the **policy engine** (`policies/policy.yaml`):

- **Action allowlists** — only permitted action types on permitted targets.
- **Protected-target deny-list** — spoofable alert fields (e.g. `srcip`) can never steer active response at loopback, the manager (agent `000`), or configured critical IPs/agents. Checked at both plan creation and execution.
- **Approver authorization** — approve/execute are authorized by Slack user ID against an approver group, with a workspace/channel allowlist.
- **Separation of duties** — the executor must differ from the approver.
- **Confidence thresholds, time windows, rate limits, idempotency** — enforced per action.

The Responder is **disabled by default** (`AUTOPILOT_RESPONDER_ENABLED`) and runs at most `MAX_CONCURRENT_EXECUTIONS` plans at once.

## Active response & verification

Agents dispatch active response through the MCP server's action tools (`block_ip`, `isolate_host`, `kill_process`, `disable_user`, `quarantine_file`, `firewall_drop`, `host_deny`, `restart_wazuh`, `active_response`). Wazuh's API returns success for *dispatch acceptance*, not on-host execution — so with `AUTOPILOT_VERIFY_ACTIONS=true` the runtime calls the declared verification tool (`check_blocked_ip`, `check_agent_isolation`, `check_file_quarantine`, …) after each action and records `verified: true|false|null` plus an explanatory note. See [POLICY_AND_APPROVALS.md](POLICY_AND_APPROVALS.md) and issue #32.

## Agent runtimes (pluggable reasoning plane)

The pipeline is runtime-agnostic. All three speak to the same MCP server and Runtime API and honor the same approval workflow — they differ only in *how* the agents are hosted.

| Runtime | Shape | Inference | Guide |
|---|---|---|---|
| **OpenClaw** (default) | 7 webhook-driven pipeline agents, 24/7 | Any provider | [openclaw/README.md](../openclaw/README.md) |
| **Hermes** (Nous Research) | 1 self-improving analyst agent + subagents; CLI/TUI + messaging gateway | Nous Portal, OpenRouter, any OpenAI-compatible endpoint | [HERMES_DEPLOYMENT.md](HERMES_DEPLOYMENT.md) |
| **NemoClaw** (NVIDIA) | OpenClaw/Hermes wrapped in the OpenShell sandbox — out-of-process policy, managed inference, snapshots | **NVIDIA stack only** — Nemotron 3 via build.nvidia.com / local NIM / Ollama-Nemotron | [NEMOCLAW_DEPLOYMENT.md](NEMOCLAW_DEPLOYMENT.md) |

Because policy enforcement and approvals live in the **Runtime Service** (not the agent), the safety guarantees hold identically regardless of which runtime — or which LLM — you choose.

## Scaling to a swarm

The seven roles scale horizontally when alert volume demands it:

- **OpenClaw** — raise `agents.defaults.maxConcurrent` and heartbeat frequency; each webhook/heartbeat run is an independent session.
- **Hermes** — the analyst spawns isolated subagents for parallel workstreams (e.g. one pivot per host).
- **NemoClaw** — run multiple OpenShell sandboxes behind the same Runtime API for fleet-style isolation (independently policed, snapshotted, rollback-able).

Whatever the fan-out, every response still funnels through the single Policy Guard gate and two-tier approval — more workers, same chain of command.

## Deployment topologies

| Topology | Inference | Network | Guide |
|---|---|---|---|
| **Cloud LLM** | OpenRouter / Anthropic / etc. | Runtime + gateway on loopback; remote access via Tailscale | [QUICKSTART.md](QUICKSTART.md) |
| **Self-hosted GPU** | vLLM (Qwen3, Llama 3.3, DeepSeek-R1) | Same | [VLLM_DEPLOYMENT.md](VLLM_DEPLOYMENT.md) |
| **Air-gapped** | Ollama, local embeddings | Zero external egress | [AIR_GAPPED_DEPLOYMENT.md](AIR_GAPPED_DEPLOYMENT.md) |
| **NVIDIA / governed** | Nemotron 3 (NIM/build.nvidia.com) | OpenShell deny-all + allowlist | [NEMOCLAW_DEPLOYMENT.md](NEMOCLAW_DEPLOYMENT.md) |

## Security boundaries

- **Gateway binds loopback only** (`127.0.0.1:18789`) — never exposed to the internet; remote access is Tailscale-only ([TAILSCALE_MANDATORY.md](TAILSCALE_MANDATORY.md)).
- **MCP reached over the Tailscale network**, authenticated by bearer token.
- **Least-privilege tools** — read-only agents are denied `write`/`exec`/`delete`/`browser`; only the response path gets `write`, only the Responder gets gated execution.
- **Untrusted alert content** — alert payloads are treated as untrusted input; agents follow prompt-injection handling in their playbooks, and the protected-target deny-list neutralizes spoofed targeting fields.
- **Fail-secure** — uncertain policy state defaults to DENY.

## Where things live

| Path | What |
|---|---|
| `runtime/autopilot-service/index.js` | Runtime service — cases, plans, policy, approvals, KPIs, evidence (~6800 LOC) |
| `runtime/autopilot-service/slack.js` | Slack Socket Mode integration |
| `runtime/autopilot-service/*.test.js` | 578 tests across 16 files |
| `openclaw/` | OpenClaw gateway config + 7 agent instruction sets |
| `hermes/`, `nemoclaw/` | Alternative runtime profiles |
| `policies/policy.yaml` | Action allowlists, approvers, protected targets, thresholds |
| `policies/toolmap.yaml` | MCP tool mappings (9 action tools + verification/rollback) |
| `playbooks/` | 7 incident-response playbooks |
| `docs/` | Full documentation set |

## Further reading

- [RUNTIME_API.md](RUNTIME_API.md) — REST API reference
- [MCP_INTEGRATION.md](MCP_INTEGRATION.md) — the 48 MCP tools and how agents call them
- [AGENT_COMMUNICATION.md](AGENT_COMMUNICATION.md) — agent ↔ runtime message flow
- [AGENT_CONFIGURATION.md](AGENT_CONFIGURATION.md) — agent files, personas, customization
- [POLICY_AND_APPROVALS.md](POLICY_AND_APPROVALS.md) — policy engine and approval workflow
- [EVIDENCE_PACK_SCHEMA.md](EVIDENCE_PACK_SCHEMA.md) — evidence pack format
- [OBSERVABILITY_EXPORT.md](OBSERVABILITY_EXPORT.md) — Prometheus metrics and SOC KPIs
