# Wazuh Autopilot — REST API (v1)

Base path `/api/v1`. JSON everywhere. Timestamps are ISO 8601 UTC strings. IDs are strings.
Auth: `Authorization: Bearer <jwt>` from `POST /auth/login`. `401` → token missing/expired (UI redirects to `/login`), `403` → missing permission (`{"detail": "missing permission: actions:approve"}`).
List endpoints return `{"items": [...], "total": n}` and accept `?limit=50&offset=0` plus the filters listed.
Live updates: `GET /api/v1/events/stream?token=<jwt>` is Server-Sent Events. Each event is `event: <type>` + `data: <json>`; types: `run.started`, `run.step`, `run.finished`, `case.created`, `case.updated`, `action.created`, `action.updated`, `alert.ingested`, `agent.status`.

## Roles & permissions (RBAC)

| Role | Label | Permissions |
|---|---|---|
| `admin` | Administrator | all |
| `soc_manager` | SOC Manager | everything except `users:manage` |
| `responder` | Incident Responder | analyst + `actions:approve`, `actions:execute` |
| `analyst` | SOC Analyst | `dashboard:read, alerts:read, cases:read, cases:write, actions:read, actions:propose, agents:read, skills:read, workflows:read, workflows:run, runs:read, runs:debug, playground:use, evals:read, standards:read` |
| `auditor` | Auditor (read-only) | every `*:read` permission + `audit:read` |

Full permission list: `dashboard:read alerts:read alerts:ingest cases:read cases:write actions:read actions:propose actions:approve actions:execute agents:read agents:write skills:read skills:write workflows:read workflows:write workflows:run runs:read runs:debug playground:use evals:read evals:run standards:read policy:read policy:write settings:read settings:write users:manage audit:read`.

The UI hides nav items / buttons the user lacks permissions for (`me.permissions`).

## Auth & users

- `POST /auth/login` `{email, password}` → `{access_token, token_type:"bearer", expires_in, user: User}`
- `GET /auth/me` → `User`
- `POST /auth/change-password` `{current_password, new_password}` → `{ok:true}`
- `GET /users` (users:manage) → list of `User`
- `POST /users` `{email, name, role, password}` → `User`
- `PATCH /users/{id}` `{name?, role?, active?, password?}` → `User`
- `DELETE /users/{id}` → `{ok:true}`
- `GET /roles` → `[{id, label, description, permissions:[...]}]`
- `GET /api-tokens` / `POST /api-tokens {name, role, expires_days}` → `{id, name, role, prefix, created_at, expires_at, token?}` (token only on create) / `DELETE /api-tokens/{id}`

`User = {id, email, name, role, role_label, permissions:[...], active, last_login_at, created_at, avatar_initials}`

## Setup (first run)

- `GET /setup/status` (no auth) → `{setup_complete: bool, demo_mode: bool, version}`
- `POST /setup/complete` (no auth, only while incomplete) `{org_name, admin_email, admin_name, admin_password, wazuh: {mcp_url, api_key}, model: ModelSettings, autonomy_level}` → `{ok:true}`

Demo mode ships a pre-created admin: `admin@autopilot.local` / `Autopilot!2026` and `setup_complete: true`.

## Dashboard

- `GET /dashboard/summary?range=24h|7d|30d` →
```json
{
  "kpis": {
    "alerts": {"value": 1284, "delta_pct": -12.4},
    "incidents": {"value": 17, "delta_pct": 25.6},
    "auto_contained": {"value": 9, "delta_pct": 46.1},
    "mttr_minutes": {"value": 14.2, "delta_pct": -8.0},
    "pending_approvals": {"value": 3, "delta_pct": 0}
  },
  "traffic": [{"ts": "...", "alerts": 120, "incidents": 2, "actions": 1, "blocked": 1}],
  "severity_breakdown": [{"severity": "critical", "count": 4}],
  "attack_sources": [{"country": "US", "country_name": "United States", "lat": 37.1, "lon": -95.7, "count": 31, "pct": 4.0}],
  "top_targets": [{"agent_id": "001", "agent_name": "web-prod-01", "ip": "10.0.1.11", "incidents": 10, "alerts": 6920, "trend_pct": 7.17}],
  "mitre_top": [{"technique_id": "T1110", "name": "Brute Force", "tactic": "Credential Access", "count": 44}],
  "swarm": {"agents_total": 12, "agents_active": 3, "runs_24h": 58, "success_rate": 0.97, "tokens_24h": 1830000, "cost_24h_usd": 12.4}
}
```
`traffic` has 24 buckets for 24h (hourly), 7/30 daily buckets otherwise.

## Alerts

- `GET /alerts?severity=&status=&q=&agent=` → `Alert[]`
- `GET /alerts/{id}` → `Alert` with `raw` (full Wazuh JSON)
- `POST /alerts/{id}/triage` (workflows:run) → `Run` (starts the triage workflow for this alert)
- `POST /ingest/wazuh` (alerts:ingest, or `X-Autopilot-Ingest-Key` header) — raw Wazuh alert JSON (or list) → `{accepted: n, case_ids: []}`

`Alert = {id, wazuh_id, ts, rule_id, rule_level, rule_description, rule_groups:[], severity: "informational|low|medium|high|critical", agent_id, agent_name, src_ip, src_country, dst_user, mitre:[{technique_id,name,tactic}], status: "new|triaged|grouped|suppressed", case_id}`

## Cases (incidents)

- `GET /cases?status=&severity=&q=&assignee=` → `Case[]`
- `GET /cases/{id}` → `CaseDetail`
- `PATCH /cases/{id}` `{status?, severity?, assignee_id?, title?}` → `CaseDetail`
- `POST /cases/{id}/comments` `{body}` → `Comment`
- `POST /cases/{id}/run` `{workflow_id}` → `Run`

`Case = {id, number:"INC-0042", title, summary, severity, status:"open|triage|investigating|contained|resolved|closed|false_positive", confidence (0-1), assignee:{id,name}|null, created_at, updated_at, alert_count, entity_count, mitre:[...], agents_involved:["triage","investigation"], pending_actions: n}`
`CaseDetail = Case + {entities:[{type:"ip|host|user|process|file|hash|domain", value, role:"attacker|victim|observed", enrichment:{}}], timeline:[{ts, kind:"alert|agent|action|comment|status", actor, text, ref_id}], findings:[{id, agent, title, body_md, standard_refs:["NIST-800-61r3:DE.AE-02"], created_at}], alerts: Alert[], actions: Action[], runs: RunSummary[], comments: Comment[]}`
`Comment = {id, author:{id,name}, body, created_at}`

## Response actions (approvals)

- `GET /actions?status=&case_id=` → `Action[]`
- `GET /actions/{id}` → `Action`
- `POST /actions/{id}/approve` `{note?}` (actions:approve) → `Action`
- `POST /actions/{id}/reject` `{reason}` (actions:approve) → `Action`
- `POST /actions/{id}/execute` (actions:execute) → `Action` (runs MCP tool + verification)
- `POST /actions/{id}/rollback` (actions:execute) → `Action`
- `GET /actions/catalog` → `[{type:"block_ip", label:"Block IP", mcp_tool:"wazuh_block_ip", verify_tool, rollback_tool, risk:"low|medium|high|critical", reversible:bool, description, d3fend:"D3-NTF"}]`

`Action = {id, case_id, case_number, type, label, target, params:{}, risk, confidence, rationale, proposed_by:"response-planner", status:"proposed|approved|rejected|executing|executed|verified|failed|rolled_back|expired", autonomy:"manual|supervised|autonomous", auto_approved: bool, approved_by:{id,name}|null, approved_at, executed_by, executed_at, result:{}, verification:{verified: bool|null, note}, created_at, expires_at}`

## Agents (swarm roster)

- `GET /agents` → `Agent[]`
- `GET /agents/{id}` → `AgentDetail`
- `PATCH /agents/{id}` (agents:write) `{enabled?, model_override?: {provider, model_id}|null, autonomy_cap?, skills?:[skill_id], tools?:[tool_name], temperature?, max_tokens?, system_prompt_extra?}` → `AgentDetail`
- `GET /agents/{id}/prompt` (runs:debug) → `{system_prompt, skills_injected:[...], tools:[{name, description, source:"mcp|platform"}]}`
- `GET /agents/{id}/health` → `AgentHealth`

`Agent = {id:"triage", name:"Tier 1 Triage Analyst", codename:"Sentinel", persona, avatar_color:"#ff8127", icon:"shield-alert" (lucide name), tier:"L1|L2|L3|lead|specialist", category:"detect|investigate|respond|intel|govern|command", enabled, status:"idle|running|error|disabled", description, skills:[{id,name}], standards:[{id, name}], tools_count, handoffs:["correlation","threat-intel"], model:{provider, model_id, inherited: bool}, autonomy_cap:"observe|recommend|supervised|autonomous", health: AgentHealth}`
`AgentDetail = Agent + {responsibilities:[str], tools:[{name, source, access:"read|verify|platform"}], recent_runs: RunSummary[], metrics_7d:[{day, runs, errors, avg_latency_ms, tokens}]}`
`AgentHealth = {status:"healthy|degraded|down|idle", score (0-100), runs_24h, error_rate, avg_latency_ms, p95_latency_ms, tokens_24h, cost_24h_usd, last_run_at, last_error: str|null}`

## Skills

- `GET /skills?category=` → `Skill[]`
- `GET /skills/{id}` → `Skill + {body_md}` (full SKILL.md instructions)
- `PUT /skills/{id}` (skills:write) `{description?, body_md?}` → Skill
- `POST /skills` (skills:write) `{id, name, description, category, body_md, standards:[]}` → Skill

`Skill = {id:"alert-triage", name, description, category:"detection|investigation|response|intel|vulnerability|compliance|reporting|safety", standards:[{id,name}], tools:[str], used_by:["triage"], builtin: bool, updated_at}`

## Standards (industry frameworks)

- `GET /standards` → `[{id:"nist-csf-2", name:"NIST CSF 2.0", publisher:"NIST", url, description, controls_mapped: n, coverage_pct, agents:[id], skills:[id]}]`
- `GET /standards/{id}` → above + `controls:[{id:"DE.AE-02", title, covered_by:[{agent|skill id}], evidence_count}]`

Frameworks: NIST CSF 2.0, NIST SP 800-61r3 (IR), NIST SP 800-53r5, MITRE ATT&CK v17, MITRE D3FEND, CIS Controls v8.1, ISO/IEC 27001:2022, PCI DSS v4.0.1, SANS PICERL, CISA KEV + FIRST EPSS + SSVC, Sigma, OWASP LLM Top 10 (agent safety).

## Workflows

- `GET /workflows` → `Workflow[]`
- `GET /workflows/{id}` → `Workflow`
- `PUT /workflows/{id}` (workflows:write) `{name?, description?, enabled?, trigger?, steps?, mode?}` → Workflow
- `POST /workflows/{id}/run` (workflows:run) `{input: {...}}` → `Run`

`Workflow = {id:"alert-to-containment", name, description, mode:"swarm|graph", enabled, trigger:{type:"alert|schedule|manual", severity_min?, cron?, rule_groups?}, entry_agent, steps:[{id, agent_id, label, next:[step_id], condition?}], last_run_at, runs_7d, success_rate}`
For `graph` mode `steps` define the DAG. For `swarm` mode `steps` lists participating agents (the entry agent hands off autonomously); `next` shows allowed handoffs.

## Runs (observability & debug)

- `GET /runs?status=&workflow_id=&agent_id=&case_id=` → `RunSummary[]`
- `GET /runs/{id}` → `Run`
- `POST /runs/{id}/cancel` → `Run`
- `POST /runs/{id}/replay` (runs:debug) → `Run` (new run, same input)

`RunSummary = {id, workflow_id, workflow_name, mode, status:"queued|running|completed|failed|cancelled", trigger:"alert|schedule|manual|playground", case_id, case_number, started_at, finished_at, duration_ms, agents:["triage",...], tokens_in, tokens_out, cost_usd, tool_calls, errors}`
`Run = RunSummary + {input:{}, output_md, handoffs:[{from, to, reason, ts}], spans: Span[]}`
`Span = {id, parent_id|null, kind:"run|agent|model|tool|handoff|guardrail", name, agent_id, status:"ok|error|blocked", started_at, duration_ms, tokens_in, tokens_out, attributes:{}, input_preview, output_preview, error|null}`
Spans form a tree for the trace waterfall view.

## Playground (agent debug)

- `POST /playground/sessions` `{agent_id, dry_run: bool}` → `{session_id, agent_id}`
- `POST /playground/sessions/{sid}/messages` `{content}` → `{run_id}`; stream progress via SSE `run.step` events filtered by `run_id`; final assistant text in `run.finished.data.output_md`
- `GET /playground/sessions/{sid}` → `{session_id, agent_id, messages:[{role:"user|assistant|tool", content, tool_name?, ts}]}`

`dry_run: true` → action tools and state-changing platform tools are stubbed.

## Evals (strands-agents-evals)

- `GET /evals/suites` → `[{id, name, agent_id, cases: n, evaluators:["ToolCalled","Contains","GoalSuccessRate"], last_score, last_run_at}]`
- `GET /evals/suites/{id}` → suite + `cases:[{name, input, expected_tools:[], expected_contains:[]}]`
- `POST /evals/suites/{id}/run` (evals:run) → `EvalRun`
- `GET /evals/runs?suite_id=` → `EvalRun[]`
- `GET /evals/runs/{id}` → `EvalRun`

`EvalRun = {id, suite_id, status, started_at, finished_at, overall_score (0-1), pass_rate, results:[{case, passed, score, evaluator_scores:{name: score}, reason, output_preview}]}`

## Governance

- `GET /policy` → `Policy`
- `PUT /policy` (policy:write) → `Policy`

`Policy = {autonomy_level:"observe|recommend|supervised|autonomous", action_rules:[{type, autonomy:"inherit|manual|supervised|autonomous", min_confidence: 0.9, max_per_hour: 10, enabled}], protected_targets:{ips:[], hosts:[], users:[], agent_ids:["000"]}, approval_expiry_minutes: 60, require_two_person: bool, business_hours_only: bool}`

Semantics: `observe` = agents analyze only, no actions proposed. `recommend` = agents propose, a human approves AND executes. `supervised` = human approves, platform executes automatically. `autonomous` = actions whose rule allows it and whose confidence ≥ min_confidence and target not protected auto-execute; everything else falls back to supervised.

- `GET /audit?actor=&action=&since=` (audit:read) → `[{id, ts, actor:{id,name,type:"user|agent|system"}, action:"action.approved", target, detail:{}, ip}]`

## Settings (configurator)

- `GET /settings` (settings:read) → `Settings` (secrets masked as `"••••last4"`)
- `PUT /settings` (settings:write) partial `Settings` → `Settings`
- `POST /settings/test/wazuh` → `{ok, latency_ms, tools_total, tools_read, tools_write, write_scope: bool, version, error?}`
- `POST /settings/test/model` `{provider?, model_id?}` → `{ok, latency_ms, provider, model_id, sample, error?}`
- `POST /settings/test/notifications` → `{ok, error?}`

```
Settings = {
  org: {name, timezone, logo_initials},
  wazuh: {mcp_url, api_key, verify_tls, toolsets:["alerts","agents","vulnerabilities","analysis","compliance","system","response"], request_timeout_s},
  model: ModelSettings,
  ingestion: {mode:"poll|webhook|both", poll_interval_s, min_level, ingest_key, dedup_window_min, group_window_min},
  notifications: {slack_webhook_url, email_to, notify_on:["critical_case","approval_needed","action_failed"]},
  observability: {otlp_endpoint, otlp_headers, prometheus_enabled, trace_retention_days},
  swarm: {max_handoffs, max_iterations, execution_timeout_s, node_timeout_s, max_concurrent_runs}
}
ModelSettings = {provider:"bedrock|anthropic|openai|vllm|litellm|ollama|demo", model_id, base_url, api_key, region, temperature, max_tokens, guardrail_id, guardrail_version, price_in_per_mtok, price_out_per_mtok}
```
- `GET /settings/providers` → `[{id:"vllm", label:"vLLM", description, fields:["base_url","model_id","api_key"], defaults:{base_url:"http://vllm:8000/v1", model_id:"Qwen/Qwen3-32B"}, local: bool}]`

## Health & metrics

- `GET /health` (no auth) → `{status:"ok", version}`
- `GET /system/health` → `{components:[{id:"api|database|wazuh_mcp|model|scheduler|ingestion", name, status:"healthy|degraded|down|unknown", latency_ms, detail, checked_at}], swarm:{agents_total, agents_healthy, runs_running, queue_depth}}`
- `GET /metrics/timeseries?metric=runs|tokens|latency|errors|cost|tool_calls&range=24h|7d&agent_id=` → `{metric, points:[{ts, value}], by_agent:[{agent_id, points:[...]}]}`
- `GET /metrics` (no `/api/v1` prefix) → Prometheus text

