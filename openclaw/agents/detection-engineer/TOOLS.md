# Detection Engineering Agent -- Tool Usage Guide

## Runtime API Access

Analysis runs through the runtime REST API at `http://localhost:9090` via `web_fetch` (GET only; token as `?token=<AUTOPILOT_MCP_AUTH>`).

### Consume rule-effectiveness & coverage inputs

Read the Reporting agent's rule-effectiveness / posture reports to find noisy rules and gaps:

    web_fetch(url="http://localhost:9090/api/reports?type=weekly&token=<AUTOPILOT_MCP_AUTH>")
    web_fetch(url="http://localhost:9090/api/reports?type=detection&token=<AUTOPILOT_MCP_AUTH>")

Read hunt reports (repeatable logic to promote) and threat-intel briefs (durable TTPs):

    web_fetch(url="http://localhost:9090/api/reports?type=hunt&token=<AUTOPILOT_MCP_AUTH>")
    web_fetch(url="http://localhost:9090/api/reports?type=threat_intel&token=<AUTOPILOT_MCP_AUTH>")

### Inspect an existing rule (for tuning)

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=rule.id:{rule_id}&time_range=30d&limit=500&token=<AUTOPILOT_MCP_AUTH>")

Use the volume and the distribution of matched fields to identify why a rule is noisy (which benign values dominate).

### Backtest a proposed detection

Translate the proposed logic into a `search-alerts` query and run it over a historical window to estimate how often it *would* have fired and against what:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query={proposed_logic_as_query}&time_range=30d&limit=500&token=<AUTOPILOT_MCP_AUTH>")

- **would_have_fired** = hit count over the window.
- **estimated_fp_rate** = inspect a sample of hits and judge how many are benign. Report `low`/`medium`/`high` with the sample basis; do not invent a precise percentage you can't support.
- Prefer logic where the benign tail is small or cleanly excludable.

## Sigma → Wazuh Mapping

- Author the detection in Sigma (portable, reviewable), then map to a Wazuh local rule:
  - Sigma `detection` fields → Wazuh `<field>`/`<match>`/`<regex>`.
  - Sigma `condition` with counts/timeframes → Wazuh `frequency` + `timeframe` (+ `if_matched_sid`/`if_matched_group`).
  - Chain off existing rules with `if_sid`/`if_group` to raise precision.
  - Set `level` per the 0–15 severity scale Triage uses.
- Keep the Sigma and the Wazuh XML in sync in the proposal so a human can review intent and implementation together.

## Detection-as-Code discipline

- Every proposal is reviewable and testable: ADS fields + Sigma + Wazuh XML + backtest result. This mirrors a detection-as-code pull request.
- Never propose deploying, editing, or deleting a live rule directly — output is a proposal for human review only. This agent has no write path to Wazuh rules by design.

## Coverage Mapping

- For each proposal, record the ATT&CK `coverage_delta` (before/after). Aggregate deltas let Reporting maintain the ATT&CK coverage heatmap and show detection-engineering progress over time.

## Cost Discipline

This agent is reactive (runs on `detection-review`, typically after Reporting's weekly cadence) — it has no fast heartbeat. Trigger it via cron/webhook aligned to the reporting cycle; see docs/HEARTBEATS_AND_COST.md.

## Stalled Pipeline Retries

If triggered with a `[RETRY]` prefix, use the pre-built callback URL from the message rather than constructing your own.
