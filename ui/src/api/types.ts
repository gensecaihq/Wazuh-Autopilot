// Types mirroring docs/API.md (v1).

export interface List<T> {
  items: T[];
  total: number;
}

export type Severity = "informational" | "low" | "medium" | "high" | "critical";
export type Risk = "low" | "medium" | "high" | "critical";
export type AutonomyLevel = "observe" | "recommend" | "supervised" | "autonomous";

// ---- Auth & users ----
export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  role_label: string;
  permissions: string[];
  active: boolean;
  last_login_at: string | null;
  created_at: string;
  avatar_initials: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface Role {
  id: string;
  label: string;
  description: string;
  permissions: string[];
}

export interface ApiToken {
  id: string;
  name: string;
  role: string;
  prefix: string;
  created_at: string;
  expires_at: string | null;
  token?: string;
}

export interface SetupStatus {
  setup_complete: boolean;
  demo_mode: boolean;
  version: string;
}

// ---- Dashboard ----
export interface Kpi {
  value: number;
  delta_pct: number;
}

export interface DashboardSummary {
  kpis: {
    alerts: Kpi;
    incidents: Kpi;
    auto_contained: Kpi;
    mttr_minutes: Kpi;
    pending_approvals: Kpi;
  };
  traffic: { ts: string; alerts: number; incidents: number; actions: number; blocked: number }[];
  severity_breakdown: { severity: Severity; count: number }[];
  attack_sources: { country: string; country_name: string; lat: number; lon: number; count: number; pct: number }[];
  top_targets: { agent_id: string; agent_name: string; ip: string; incidents: number; alerts: number; trend_pct: number }[];
  mitre_top: { technique_id: string; name: string; tactic: string; count: number }[];
  swarm: {
    agents_total: number;
    agents_active: number;
    runs_24h: number;
    success_rate: number;
    tokens_24h: number;
    cost_24h_usd: number;
  };
}

// ---- Alerts ----
export interface Mitre {
  technique_id: string;
  name: string;
  tactic: string;
}

export interface Alert {
  id: string;
  wazuh_id: string;
  ts: string;
  rule_id: string;
  rule_level: number;
  rule_description: string;
  rule_groups: string[];
  severity: Severity;
  agent_id: string;
  agent_name: string;
  src_ip: string | null;
  src_country: string | null;
  dst_user: string | null;
  mitre: Mitre[];
  status: "new" | "triaged" | "grouped" | "suppressed";
  case_id: string | null;
  raw?: Record<string, unknown>;
}

// ---- Cases ----
export type CaseStatus =
  | "open"
  | "triage"
  | "investigating"
  | "contained"
  | "resolved"
  | "closed"
  | "false_positive";

export interface PersonRef {
  id: string;
  name: string;
}

export interface Case {
  id: string;
  number: string;
  title: string;
  summary: string;
  severity: Severity;
  status: CaseStatus;
  confidence: number;
  assignee: PersonRef | null;
  created_at: string;
  updated_at: string;
  alert_count: number;
  entity_count: number;
  mitre: Mitre[];
  agents_involved: string[];
  pending_actions: number;
}

export interface Entity {
  type: "ip" | "host" | "user" | "process" | "file" | "hash" | "domain";
  value: string;
  role: "attacker" | "victim" | "observed";
  enrichment: Record<string, unknown>;
}

export interface TimelineItem {
  ts: string;
  kind: "alert" | "agent" | "action" | "comment" | "status";
  actor: string;
  text: string;
  ref_id: string | null;
}

export interface Finding {
  id: string;
  agent: string;
  title: string;
  body_md: string;
  standard_refs: string[];
  created_at: string;
}

export interface Comment {
  id: string;
  author: PersonRef;
  body: string;
  created_at: string;
}

export interface CaseDetail extends Case {
  entities: Entity[];
  timeline: TimelineItem[];
  findings: Finding[];
  alerts: Alert[];
  actions: Action[];
  runs: RunSummary[];
  comments: Comment[];
}

// ---- Actions ----
export type ActionStatus =
  | "proposed"
  | "approved"
  | "rejected"
  | "executing"
  | "executed"
  | "verified"
  | "failed"
  | "rolled_back"
  | "expired";

export interface Action {
  id: string;
  case_id: string;
  case_number: string;
  type: string;
  label: string;
  target: string;
  params: Record<string, unknown>;
  risk: Risk;
  confidence: number;
  rationale: string;
  proposed_by: string;
  status: ActionStatus;
  autonomy: "manual" | "supervised" | "autonomous";
  auto_approved: boolean;
  approved_by: PersonRef | null;
  approved_at: string | null;
  executed_by: PersonRef | string | null;
  executed_at: string | null;
  result: Record<string, unknown>;
  verification: { verified: boolean | null; note: string } | null;
  created_at: string;
  expires_at: string | null;
}

export interface ActionCatalogItem {
  type: string;
  label: string;
  mcp_tool: string;
  verify_tool: string | null;
  rollback_tool: string | null;
  risk: Risk;
  reversible: boolean;
  description: string;
  d3fend: string;
}

// ---- Agents ----
export interface AgentHealth {
  status: "healthy" | "degraded" | "down" | "idle";
  score: number;
  runs_24h: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  tokens_24h: number;
  cost_24h_usd: number;
  last_run_at: string | null;
  last_error: string | null;
}

export interface Ref {
  id: string;
  name: string;
}

export interface Agent {
  id: string;
  name: string;
  codename: string;
  persona: string;
  avatar_color: string;
  icon: string;
  tier: "L1" | "L2" | "L3" | "lead" | "specialist";
  category: "detect" | "investigate" | "respond" | "intel" | "govern" | "command";
  enabled: boolean;
  status: "idle" | "running" | "error" | "disabled";
  description: string;
  skills: Ref[];
  standards: Ref[];
  tools_count: number;
  handoffs: string[];
  model: { provider: string; model_id: string; inherited: boolean };
  autonomy_cap: AutonomyLevel;
  health: AgentHealth;
}

export interface AgentDetail extends Agent {
  responsibilities: string[];
  tools: { name: string; source: "mcp" | "platform"; access: "read" | "verify" | "platform" }[];
  recent_runs: RunSummary[];
  metrics_7d: { day: string; runs: number; errors: number; avg_latency_ms: number; tokens: number }[];
}

export interface AgentPatch {
  enabled?: boolean;
  model_override?: { provider: string; model_id: string } | null;
  autonomy_cap?: AutonomyLevel;
  skills?: string[];
  tools?: string[];
  temperature?: number;
  max_tokens?: number;
  system_prompt_extra?: string;
}

export interface AgentPrompt {
  system_prompt: string;
  skills_injected: string[];
  tools: { name: string; description: string; source: "mcp" | "platform" }[];
}

// ---- Skills ----
export type SkillCategory =
  | "detection"
  | "investigation"
  | "response"
  | "intel"
  | "vulnerability"
  | "compliance"
  | "reporting"
  | "safety";

export interface Skill {
  id: string;
  name: string;
  description: string;
  category: SkillCategory;
  standards: Ref[];
  tools: string[];
  used_by: string[];
  builtin: boolean;
  updated_at: string;
  body_md?: string;
}

// ---- Standards ----
export interface Standard {
  id: string;
  name: string;
  publisher: string;
  url: string;
  description: string;
  controls_mapped: number;
  coverage_pct: number;
  agents: string[];
  skills: string[];
}

export interface StandardDetail extends Standard {
  controls: { id: string; title: string; covered_by: string[]; evidence_count: number }[];
}

// ---- Workflows ----
export interface WorkflowStep {
  id: string;
  agent_id: string;
  label: string;
  next: string[];
  condition?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  mode: "swarm" | "graph";
  enabled: boolean;
  trigger: { type: "alert" | "schedule" | "manual"; severity_min?: Severity; cron?: string; rule_groups?: string[] };
  entry_agent: string;
  steps: WorkflowStep[];
  last_run_at: string | null;
  runs_7d: number;
  success_rate: number;
}

// ---- Runs ----
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface RunSummary {
  id: string;
  workflow_id: string;
  workflow_name: string;
  mode: "swarm" | "graph" | "single";
  status: RunStatus;
  trigger: "alert" | "schedule" | "manual" | "playground";
  case_id: string | null;
  case_number: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  agents: string[];
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  tool_calls: number;
  errors: number;
}

export interface Span {
  id: string;
  parent_id: string | null;
  kind: "run" | "agent" | "model" | "tool" | "handoff" | "guardrail";
  name: string;
  agent_id: string | null;
  status: "ok" | "error" | "blocked";
  started_at: string;
  duration_ms: number;
  tokens_in: number;
  tokens_out: number;
  attributes: Record<string, unknown>;
  input_preview: string | null;
  output_preview: string | null;
  error: string | null;
}

export interface Run extends RunSummary {
  input: Record<string, unknown>;
  output_md: string | null;
  handoffs: { from: string; to: string; reason: string; ts: string }[];
  spans: Span[];
}

// ---- Playground ----
export interface PlaygroundMessage {
  role: "user" | "assistant" | "tool";
  content: string;
  tool_name?: string;
  ts: string;
}

export interface PlaygroundSession {
  session_id: string;
  agent_id: string;
  messages: PlaygroundMessage[];
}

// ---- Evals ----
export interface EvalSuite {
  id: string;
  name: string;
  agent_id: string;
  cases: number;
  evaluators: string[];
  last_score: number | null;
  last_run_at: string | null;
}

export interface EvalSuiteDetail extends Omit<EvalSuite, "cases"> {
  cases: { name: string; input: string; expected_tools: string[]; expected_contains: string[] }[];
}

export interface EvalRun {
  id: string;
  suite_id: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  overall_score: number | null;
  pass_rate: number | null;
  results: {
    case: string;
    passed: boolean;
    score: number;
    evaluator_scores: Record<string, number>;
    reason: string;
    output_preview: string;
  }[];
}

// ---- Governance ----
export interface ActionRule {
  type: string;
  autonomy: "inherit" | "manual" | "supervised" | "autonomous";
  min_confidence: number;
  max_per_hour: number;
  enabled: boolean;
}

export interface Policy {
  autonomy_level: AutonomyLevel;
  action_rules: ActionRule[];
  protected_targets: { ips: string[]; hosts: string[]; users: string[]; agent_ids: string[] };
  approval_expiry_minutes: number;
  require_two_person: boolean;
  business_hours_only: boolean;
}

export interface AuditEntry {
  id: string;
  ts: string;
  actor: { id: string; name: string; type: "user" | "agent" | "system" };
  action: string;
  target: string;
  detail: Record<string, unknown>;
  ip: string | null;
}

// ---- Settings ----
export type ProviderId = "bedrock" | "anthropic" | "openai" | "nvidia_nim" | "vllm" | "litellm" | "ollama" | "demo";

export interface ModelSettings {
  provider: ProviderId;
  model_id: string;
  base_url: string;
  api_key: string;
  region: string;
  temperature: number;
  max_tokens: number;
  guardrail_id: string;
  guardrail_version: string;
  price_in_per_mtok: number;
  price_out_per_mtok: number;
  context_window?: number;
}

export interface Settings {
  org: { name: string; timezone: string; logo_initials: string };
  wazuh: { mcp_url: string; api_key: string; verify_tls: boolean; toolsets: string[]; request_timeout_s: number };
  model: ModelSettings;
  ingestion: {
    mode: "poll" | "webhook" | "both";
    poll_interval_s: number;
    min_level: number;
    ingest_key: string;
    dedup_window_min: number;
    group_window_min: number;
  };
  notifications: { slack_webhook_url: string; email_to: string; notify_on: string[] };
  observability: { otlp_endpoint: string; otlp_headers: string; prometheus_enabled: boolean; trace_retention_days: number };
  swarm: {
    max_handoffs: number;
    max_iterations: number;
    execution_timeout_s: number;
    node_timeout_s: number;
    max_concurrent_runs: number;
  };
}

export interface ProviderInfo {
  id: ProviderId;
  label: string;
  description: string;
  fields: (keyof ModelSettings)[];
  defaults: Partial<ModelSettings>;
  local: boolean;
}

export interface WazuhTestResult {
  ok: boolean;
  latency_ms: number;
  tools_total: number;
  tools_read: number;
  tools_write: number;
  write_scope: boolean;
  version: string;
  error?: string;
}

export interface ModelTestResult {
  ok: boolean;
  latency_ms: number;
  provider: string;
  model_id: string;
  sample: string;
  error?: string;
}

// ---- Health & metrics ----
export interface SystemHealth {
  components: {
    id: string;
    name: string;
    status: "healthy" | "degraded" | "down" | "unknown";
    latency_ms: number | null;
    detail: string;
    checked_at: string;
  }[];
  swarm: { agents_total: number; agents_healthy: number; runs_running: number; queue_depth: number };
}

export type MetricName = "runs" | "tokens" | "latency" | "errors" | "cost" | "tool_calls";

export interface Timeseries {
  metric: MetricName;
  points: { ts: string; value: number }[];
  by_agent: { agent_id: string; points: { ts: string; value: number }[] }[];
}

// ---- SSE ----
export type SseType =
  | "run.started"
  | "run.step"
  | "run.finished"
  | "case.created"
  | "case.updated"
  | "action.created"
  | "action.updated"
  | "alert.ingested"
  | "agent.status";

export interface SseEvent {
  type: SseType;
  data: Record<string, unknown>;
  at: number;
}
