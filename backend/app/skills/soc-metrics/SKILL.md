---
name: soc-metrics
description: Calculate and interpret SOC performance metrics — MTTD, MTTA, MTTR, MTTC, alert-to-incident ratio, false-positive and automation rates, and agent cost/latency — with maturity context; use for KPI reporting and SOC performance questions.
allowed-tools: search_cases get_case list_actions get_wazuh_alert_summary get_wazuh_statistics save_report
metadata:
  category: reporting
  display_name: SOC Metrics
  standards: [nist-csf-2, nist-800-61r3]
  version: "1.1"
---
# SOC Metrics

Metrics should drive improvement, not vanity. Define precisely, compute consistently,
and always show the trend and the sample size.

## Time metrics (per incident, then median and p90 over the period)

| Metric | Definition | Start → End |
|---|---|---|
| MTTD — mean time to detect | how long the attacker was active before detection | first malicious activity → first alert |
| MTTA — mean time to acknowledge | time until someone (agent or human) started work | case created → first triage finding |
| MTTC — mean time to contain | time to stop the harm | case created → containment verified |
| MTTR — mean time to respond/resolve | time to close out | case created → resolved/closed |

Report **median and p90** alongside the mean — a few long incidents skew means. MTTD
requires an incident timeline; mark it "n/a" where the start of malicious activity is
unknown.

## Volume and quality

| Metric | Formula | Healthy signal |
|---|---|---|
| Alert-to-incident ratio | alerts ingested ÷ cases opened | falling over time with stable coverage |
| False-positive rate | cases closed `false_positive` ÷ cases closed | trending down; > 50% means tuning needed |
| Escalation rate | cases reaching investigation ÷ cases opened | stable, explainable |
| Automation rate | actions auto-approved or auto-executed ÷ all executed actions | increases only with low rollback rate |
| Rollback rate | actions rolled back ÷ executed | < 5%; spikes mean over-aggressive autonomy |
| Verification rate | executed actions verified ÷ executed | → 100% |
| Approval latency | action proposed → approved (median) | within policy expiry |
| Agent coverage | active Wazuh agents ÷ expected assets | → 100% |
| Telemetry loss | alerts for rule 203 (event queue full) or rule 204 (queue flooded), and agents disconnected for > 1h (rule 504) | zero; any non-zero means detection blind spots. Get detail from `platform-engineer` |
| MTTD | first attacker event time (from the log, not the alert `timestamp`) → case opened | falling; ingestion delay shows up as the gap between event time and alert time |

## Agent (swarm) performance

Per agent: runs, error rate, median/p95 latency, tokens in/out, cost per run and per
incident. Flag agents whose cost per incident rises without better outcomes, or whose
error rate > 5%.

## Interpretation

- Always compare with the previous equal period and state the sample size.
- A metric moving the "good" way can be bad: a falling FP rate plus falling incidents may
  mean a detection broke. Cross-check with alert volume and agent coverage.
- SOC-CMM style maturity hints: consistent metric definitions, trend review in a regular
  meeting, and metrics tied to improvement actions indicate a managed (level 3+)
  process; ad-hoc or unreviewed metrics indicate initial/defined levels.

## Output format

```
| Metric | This period | Previous | Change | n |
```

Follow with 3 bullet insights and 1–3 recommendations.

## Output

- `save_report(kind="weekly"|"monthly", title, body_md)` or include the table in the
  report being written by `executive-reporting`. standard_refs: `NIST-CSF-2:ID.IM`
  (improvement).
