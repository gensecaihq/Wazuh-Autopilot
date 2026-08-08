# Policy and Approval System

Wazuh Autopilot implements an enterprise-grade policy engine that controls all automated actions. This document explains how policies work and how to configure them.

## Core Principles

1. **Deny by Default** - Actions require explicit enablement
2. **Separation of Duties** - Different agents have different permissions
3. **Audit Trail** - Every decision is logged with reason codes
4. **Configurable Autonomy** - Balance automation with human oversight
5. **Inline Enforcement** - Policies are enforced at the Runtime Service level, not just by agents

## Enforcement Architecture

Policy enforcement operates at **two levels**:

### 1. Runtime-Level (Inline) — Primary

The Runtime Service enforces `policies/policy.yaml` at six critical points:

| Enforcement Point | API Endpoint | What's Checked |
|-------------------|-------------|----------------|
| **Plan Creation** | `POST /api/plans` | Each action validated against `actions.allowlist` — must be `enabled`, must meet `min_confidence`. Time window check for `response_planning` operation. |
| **Plan Approval** | `POST /api/plans/:id/approve` | Approver validated against `approvers.groups` — must have action in `can_approve`, risk level must be within `max_risk_level` |
| **Plan Execution (pre-loop)** | `POST /api/plans/:id/execute` | Evidence count validated against `min_evidence_items`. Time window check for `action_execution` operation — denies entire plan if outside window. |
| **Plan Execution (per-action)** | `POST /api/plans/:id/execute` | Each action checked for **idempotency** (duplicate action+target within window) and **rate limits** (per-action and global hourly/daily). Denied actions are skipped individually. |

**Fail modes:**
- **Production mode** (`AUTOPILOT_MODE=production`): Fail-closed — denies if policy cannot be loaded
- **Bootstrap mode** (`AUTOPILOT_MODE=bootstrap`): Fail-open — warns but allows (easier testing)

### 2. Agent-Level (Supplementary) — Advisory

The Policy Guard agent is still triggered via webhook when a plan is created. It performs supplementary LLM-based analysis (blast radius assessment, context-aware evaluation) that complements the rule-based inline checks. Its findings are advisory — the Runtime's inline enforcement is authoritative.

## Autonomy Levels

Autopilot supports three autonomy levels:

### Read-Only (Default for most agents)

- Can query Wazuh data via MCP
- Can create and update cases
- Can post to Slack
- **Cannot** execute response actions

### Approval (Default for response actions)

- All capabilities of read-only
- Can propose response plans
- Can request approvals
- Executes actions **only after approval**

### Limited-Auto (Optional)

- Executes pre-approved safe actions automatically
- Still requires approval for risky actions
- Must be explicitly enabled

## Policy Configuration

All policies are defined in `policies/policy.yaml`. This file is the **source of truth** for all policy decisions.

### Autonomy Settings

```yaml
autonomy:
  default_level: approval

  operations:
    triage:
      level: read-only
      auto_execute: true

    response_planning:
      level: approval
      auto_execute: false

    action_execution:
      level: approval
      auto_execute: false
```

### Slack Allowlists

Control where Autopilot can operate:

```yaml
slack:
  workspace_allowlist:
    - id: "T0123456789"
      name: "Security Team"
      enabled: true

  channels:
    alerts:
      allowlist:
        - id: "C0123456789"
          name: "#security-alerts"
      deny_action: log_and_skip

    approvals:
      allowlist:
        - id: "C1234567890"
          name: "#security-approvals"
      deny_action: log_and_skip
```

### Approver Configuration

Define who can approve what:

```yaml
approvers:
  groups:
    standard:
      members:
        - slack_id: "U0123456789"
          name: "Security Analyst"
      can_approve:
        - block_ip
        - quarantine_file
      max_risk_level: medium

    elevated:
      members:
        - slack_id: "U1234567890"
          name: "Senior Engineer"
      can_approve:
        - block_ip
        - isolate_host
        - kill_process
      max_risk_level: high

    admin:
      members:
        - slack_id: "U2345678901"
          name: "Security Director"
      can_approve:
        - block_ip
        - quarantine_file
        - isolate_host
        - kill_process
        - disable_user
        - firewall_drop
        - host_deny
        - active_response
        - restart_wazuh
      max_risk_level: critical

  self_approval:
    allowed: false
```

### Action Allowlists

Control which actions are permitted:

```yaml
actions:
  enabled: true  # Actions enabled - individual actions still require approval

  allowlist:
    block_ip:
      enabled: true
      risk_level: low
      requires_approval: true
      min_approver_group: standard
      min_confidence: 0.7
      min_evidence_items: 2

    isolate_host:
      enabled: true
      risk_level: medium
      requires_approval: true
      min_approver_group: elevated
      min_confidence: 0.8
      min_evidence_items: 3

    disable_user:
      enabled: true
      risk_level: high
      requires_approval: true
      min_approver_group: admin
      min_confidence: 0.9
      min_evidence_items: 5

  deny_unlisted: true
```

### Asset Criticality

Different rules for different asset types:

```yaml
assets:
  classifications:
    critical:
      patterns:
        hostnames:
          - "^prod-.*"
          - "^db-.*"
        ips:
          - "10.0.1.0/24"
      requires_approver_group: admin
      extra_evidence_required: 2

    production:
      patterns:
        hostnames:
          - "^app-.*"
          - "^web-.*"
      requires_approver_group: elevated

    development:
      patterns:
        hostnames:
          - "^dev-.*"
          - "^test-.*"
      requires_approver_group: standard

  default_classification: production
```

### Thresholds

Minimum requirements for different operations:

```yaml
thresholds:
  evidence:
    action_execution:
      min_items: 3

  confidence:
    action_execution:
      min: 0.7
    critical_action:
      min: 0.9
```

### Time Windows (Optional)

Restrict operations to certain times. **Enforced at runtime** — the runtime checks `policyCheckTimeWindow()` before plan creation and execution.

```yaml
time_windows:
  enabled: true  # false by default — set to true to activate

  operations:
    action_execution:
      windows:
        - days: [mon, tue, wed, thu, fri]
          start: "06:00"
          end: "22:00"
          timezone: UTC
      outside_window_action: deny  # "deny" blocks, "allow" permits

    response_planning:
      windows:
        - days: [mon, tue, wed, thu, fri, sat, sun]
          start: "00:00"
          end: "23:59"
          timezone: UTC
      outside_window_action: allow

  emergency_override:
    enabled: true
    requires_approver_group: admin
    max_duration_hours: 4
```

**Enforcement behavior:**
- `response_planning` is checked during `POST /api/plans` (plan creation). If denied, the plan is not created and the API returns 400.
- `action_execution` is checked during `POST /api/plans/:id/execute` (before the action loop). If denied, the entire plan is marked FAILED — no actions execute.
- When `outside_window_action: allow`, operations outside the window are permitted with a log warning.
- When `time_windows.enabled: false` (the default), all time window checks are no-ops.

### Rate Limits

Control how many actions can execute per time period. **Enforced at runtime** — the runtime checks `policyCheckActionRateLimit()` before each action in the execution loop.

```yaml
rate_limits:
  # Per-action rate limits
  actions:
    block_ip:
      max_per_hour: 100
      max_per_day: 500
    isolate_host:
      max_per_hour: 20
      max_per_day: 50
    disable_user:
      max_per_hour: 10
      max_per_day: 30

  # Global rate limits (across all action types)
  global:
    max_actions_per_hour: 200
    max_actions_per_day: 1000
```

**Enforcement behavior:**
- Counters increment **only after successful** MCP tool execution (failed actions don't consume budget)
- Per-action and global limits are checked independently — either can deny
- When a rate limit is exceeded, the individual action is skipped with `status: "denied"` in the execution results; the plan continues with remaining actions
- Counter windows auto-reset when they expire (hourly/daily)
- Stale counter entries are evicted every 5 minutes
- Actions not listed in `rate_limits.actions` are still subject to global limits

### Idempotency / Duplicate Detection

Prevent the same action from executing repeatedly on the same target. **Enforced at runtime** — the runtime checks `policyCheckIdempotency()` before each action in the execution loop.

```yaml
idempotency:
  enabled: true  # true by default

  # State checks (declarative labels for documentation)
  checks:
    block_ip:
      check_method: verify_ip_not_blocked
      deny_if_exists: true
      deny_reason: ALREADY_BLOCKED
    isolate_host:
      check_method: verify_host_not_isolated
      deny_if_exists: true
      deny_reason: ALREADY_ISOLATED

  # Duplicate request detection (enforced at runtime)
  duplicate_detection:
    enabled: true
    window_minutes: 60     # Deny same action+target within this window
    deny_reason: DUPLICATE_REQUEST
```

**Enforcement behavior:**
- The runtime tracks `action_type:target` pairs with timestamps
- If the same action+target was successfully executed within `window_minutes`, the action is denied with `DUPLICATE_REQUEST`
- Different targets for the same action type are allowed (e.g., `block_ip:10.0.0.1` and `block_ip:10.0.0.2` are independent)
- Denied actions are skipped individually with `status: "denied"` — the plan continues
- Dedup entries are recorded **only after successful** execution
- Stale entries are evicted every 5 minutes
- Maximum 10,000 dedup entries tracked (LRU eviction)

## Approval Workflow

### 1. Response Planner Creates Plan

When a case reaches high/critical severity, the Response Planner agent generates a plan:

```json
{
  "plan_id": "PLAN-20260217-abc12345",
  "case_id": "CASE-20260217-abc12345",
  "actions": [
    {
      "action": "block_ip",
      "target": "192.168.1.100",
      "risk_level": "low"
    }
  ],
  "risk_assessment": {...},
  "blast_radius": {...}
}
```

### 2. Inline Policy Enforcement (Automatic)

The Runtime Service enforces policy rules before the plan is stored:

```
Inline Enforcement (plan creation):
1. ✓ Time window check (response_planning within allowed hours)
2. ✓ Action allowlist (block_ip enabled)
3. ✓ Confidence threshold (0.85 >= 0.7)
4. ✓ deny_unlisted check (action is listed)

Result: ALLOW (plan created, webhook dispatched to Policy Guard)
```

### 2b. Policy Guard Evaluates (Supplementary)

The Policy Guard agent receives a webhook and performs LLM-based analysis:

```
Supplementary Analysis:
1. ✓ Asset criticality (dev system, standard ok)
2. ✓ Evidence threshold (3 items >= 2 required)
3. ✓ Blast radius assessment
4. ✓ Context-aware risk evaluation

Result: ADVISORY — findings added to case
```

> **Note:** Time window, rate limit, and idempotency checks are now enforced by the Runtime Service (not the Policy Guard agent). The Policy Guard provides supplementary LLM analysis only.

### 3. Approval Request Posted

An approval request is posted to Slack:

```
🚨 Approval Request

Case: CASE-20260217-abc12345
Severity: High
Confidence: 85%

Proposed Actions:
1. Block IP 192.168.1.100 (risk: low)

Risk Assessment:
- Blast radius: 1 host affected
- Reversible: Yes

Evidence:
- 47 brute force attempts
- 3 source IPs correlated
- Pattern matches known attack

Required Approver: standard or higher

[Approve (Tier 1)] [Reject]
```

### 4. Approver Responds

The approver clicks **Approve (Tier 1)** or uses:

```
/wazuh approve PLAN-20260217-abc12345
```

### 5. Approver Authorization Checked

On approval, the runtime verifies (`policyCheckApprover`):
- The approver's Slack ID belongs to an approver group in `policy.yaml`
- That group's `max_risk_level` covers the plan's risk level
- That group's `can_approve` list covers every action type in the plan

For Slack approvals, the workspace and channel are additionally checked against the
`slack` allowlists in `policy.yaml` (`policyCheckSlackContext`).

If every approver Slack ID in `policy.yaml` is still a placeholder (development /
bootstrap), the check denies by default unless `AUTOPILOT_BOOTSTRAP_APPROVAL=true`
is set explicitly.

> **Note:** The runtime contains single-use approval-token scaffolding
> (`generateApprovalToken` / `validateApprovalToken` / `consumeApprovalToken`), but it
> is **not wired into the approval flow**. Authorization is enforced through approver-group
> membership as described above, plus separation of duties at execution time.

### 6. Execution Requested (Tier 2)

Execution is a second, separate human step. The runtime enforces separation of duties:
the executor must be a different person from the approver (`"Executor must be different
from approver (separation of duties)"`), and each action is re-checked against the time
window, rate limits, idempotency window, and the protected-target deny-list.

### 7. Action Executed (If Enabled)

If the Responder agent is enabled:
- Action is executed via MCP
- Result is verified
- Evidence pack is updated
- Confirmation posted to Slack

## Deny Reason Codes

Every policy denial is counted in the `autopilot_policy_denies_total` metric with one of
these `reason` labels (exactly as emitted by the runtime):

| Reason label | Description | Enforcement Point |
|------|-------------|-------------------|
| `action_denied` | Action type not in allowlist, actions globally disabled, or confidence below the configured minimum | Runtime (plan creation) |
| `protected_target` | Target IP/CIDR or agent ID is on the `protected_targets` deny-list | Runtime (plan creation and execution) |
| `time_window_denied` | Operation outside allowed hours | Runtime (plan creation and execution) |
| `approver_denied` | Approver lacks group membership, risk-level clearance, or action authorization | Runtime (plan approval) |
| `insufficient_evidence` | Not enough evidence items | Runtime (plan execution) |
| `duplicate_action` | Same action+target within dedup window | Runtime (per-action execution) |
| `action_rate_limited` | Per-action hourly/daily limit exceeded | Runtime (per-action execution) |
| `global_rate_limited` | Global hourly/daily limit exceeded | Runtime (per-action execution) |

Slack workspace/channel allowlist failures are rejected at the Slack layer with a
descriptive error message (no metric label). The approval-token reason codes
(`EXPIRED_APPROVAL`, `INVALID_APPROVAL_TOKEN`, …) belong to the inactive token
scaffolding and are never emitted in the live flow.

## Metrics

Policy decisions are tracked via Prometheus metrics:

```
autopilot_policy_denies_total{reason="insufficient_evidence"}
autopilot_policy_denies_total{reason="approver_denied"}
autopilot_policy_denies_total{reason="action_denied"}
autopilot_policy_denies_total{reason="protected_target"}
autopilot_policy_denies_total{reason="time_window_denied"}
autopilot_policy_denies_total{reason="action_rate_limited"}
autopilot_policy_denies_total{reason="global_rate_limited"}
autopilot_policy_denies_total{reason="duplicate_action"}
```

## Best Practices

### Start Restrictive

Begin with conservative settings:

```yaml
# In policy.yaml — actions require individual enablement and human approval
actions:
  enabled: true
  # Each action in the allowlist must have enabled: true to be available
  # All actions require human approval regardless of this flag

autonomy:
  default_level: approval
```

Additionally, keep the responder capability disabled until ready:

```bash
# In .env — blocks execution even after human approval
AUTOPILOT_RESPONDER_ENABLED=false
```

### Test in Bootstrap Mode

Use bootstrap mode for testing without Tailscale requirements.

### Review Deny Rates

Monitor `autopilot_policy_denies_total` to identify:
- Over-restrictive policies
- Training needs for approvers
- Potential configuration issues

### Regular Policy Review

Schedule quarterly reviews of:
- Approver lists
- Action allowlists
- Threshold values
- Time windows

### Document Exceptions

When making policy exceptions:
1. Document the business justification
2. Set an expiration date
3. Review during next policy audit

## Troubleshooting

### "Action not allowed"

1. Check `actions.enabled` is `true`
2. Verify action is in `allowlist`
3. Check action's `enabled` is `true`

### "Approver not authorized"

1. Verify approver's Slack ID in policy
2. Check approver is in correct group
3. Verify group can approve this action type

### "Insufficient evidence"

1. Lower threshold temporarily for testing
2. Ensure triage/investigation completed
3. Review evidence collection in playbook

### Self-approval issues

If legitimate need for self-approval:

```yaml
approvers:
  self_approval:
    allowed: true
    exception_groups:
      - admin
```

**Not recommended** - breaks separation of duties.
