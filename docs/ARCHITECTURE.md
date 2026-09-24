# Architecture

Wazuh Autopilot is one Python service (FastAPI + [Strands Agents](https://strandsagents.com)) with a React console, backed by Postgres (SQLite for development). Wazuh is reached only through the [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server). Strands is the only agent engine.

```
                     ┌──────────────────────────── Autopilot container ───────────────────────────┐
 Wazuh manager       │                                                                              │
     │               │  ingestion ──► incidents ──► orchestrator ──► Strands Swarm / Graph          │
     ▼               │  (poll/webhook)   (grouping)     (worker pool)    13 agents, 37 skills        │
 Wazuh MCP Server ◄──┼── agents' MCP client (read + wazuh_check_* only)          │ propose_action     │
  (55 tools)    ◄──┐ │                                                         ▼                    │
                   └─┼── executor ◄── approved ◄── autonomy policy ◄── action proposals             │
                     │      │ verify · rollback          ▲ humans (approvals queue, RBAC)            │
                     │      ▼                            │                                          │
                     │  audit log · traces (spans) · metrics · SSE ──► console (React)              │
                     └──────────────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Code | Role |
|---|---|---|
| API | `backend/app/api/` | REST API (`/api/v1`), SSE event stream, OpenAPI at `/api/docs` |
| Ingestion | `backend/app/ingest.py` | Polls `get_wazuh_alerts` through MCP or accepts webhooks; normalizes alerts; groups them into incidents by rule + source within a window; starts workflows under an hourly run budget |
| Orchestrator | `backend/app/orchestrator.py` | Worker pool that runs workflows as a Strands `Swarm` (handoffs) or `Graph` (fixed DAG), single-agent playground turns, and action execution; cancellation and restart recovery |
| Agent factory | `backend/app/swarm/factory.py` | Builds each Strands `Agent` from its roster entry: system prompt, model, allowed tools, `AgentSkills` plugin, hooks |
| MCP client | `backend/app/swarm/mcp.py` | Streamable HTTP client with JWT exchange (`/auth/token`). The agents' client filters out state-changing tools; the executor's client doesn't |
| Platform tools | `backend/app/swarm/tools.py` | Case, entity, ATT&CK, finding, action-proposal, report and detection tools, attributed to the calling agent and run |
| Policy engine | `backend/app/policy.py` | Decides whether a proposal is refused, needs a human, or can run autonomously |
| Executor | `backend/app/executor.py` | Runs approved actions through MCP, verifies with `wazuh_check_*`, rolls back, and starts the Responder's post-action workflow |
| Tracing | `backend/app/swarm/telemetry.py` | Strands hooks → spans (agent, model, tool, handoff, guardrail) with tokens and latency; live SSE; optional OTLP export |
| Evals | `backend/app/evals.py` | `strands-agents-evals` suites run in dry-run mode |
| Console | `ui/` | Vite + React + Tailwind, served by the backend |

## Incident lifecycle

1. An alert at or above `min_level` arrives. If an open incident with the same rule and source was updated within `group_window_min`, the alert joins it. Otherwise a new incident (`INC-0001`, …) is opened with initial entities and ATT&CK techniques from the alert.
2. The matching alert workflow starts: **Alert → Containment** (swarm) for high and critical, **Alert triage** (graph) for medium.
3. Agents query Wazuh through MCP, record entities, ATT&CK techniques and findings, hand off to each other, and the IR lead calls `propose_action`.
4. The policy engine refuses the proposal (observe mode, protected target, disabled action), queues it for a human, or approves it autonomously.
5. The executor runs approved actions, verifies them on the endpoint, records the result, and starts the Responder's verification workflow. Everything is written to the audit log and the incident timeline.

## Security boundaries

- **Agents can't change Wazuh state.** State-changing `wazuh_*` tools are removed from the agents' MCP tool list, and an `ApprovalGate` hook cancels any that slip through. Only the executor calls them, and only for approved actions.
- **Alert content is untrusted.** Alerts are passed between markers, and every agent carries the `prompt-injection-defense` skill (OWASP LLM01/LLM06).
- **Fail-secure policy.** Unknown or disabled actions and protected targets are refused. Critical-risk actions never run autonomously.
- **RBAC everywhere.** Five roles, scoped API tokens, full audit log.
- **Secrets** are stored server-side and masked in the API. The container runs as non-root, and the port binds to `127.0.0.1` by default. Tokens passed as `?token=` (SSE) are redacted from access logs.

## Data model

Postgres tables: `users`, `api_tokens`, `settings` (one JSON row per section), `agents`, `skills` (custom and edited skills), `workflows`, `alerts`, `cases`, `timeline`, `findings`, `comments`, `actions`, `runs`, `spans`, `audit_log`, `reports`, `detections`, `playground_sessions`, `eval_suites`, `eval_runs`. The schema is created on boot. Built-in agents, workflows and eval suites are added if missing and upgraded field by field on boot; fields an admin customized are kept.
