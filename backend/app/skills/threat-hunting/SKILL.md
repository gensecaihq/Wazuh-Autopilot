---
name: threat-hunting
description: Run hypothesis-driven threat hunts over Wazuh data using the PEAK framework (hypothesis, baseline, model-assisted), record outcomes, and hand confirmed patterns to detection engineering; use for scheduled hunts or when asked to look for undetected activity.
allowed-tools: search_security_events get_wazuh_alerts get_alerts_aggregated analyze_alert_patterns get_wazuh_rules_summary get_sca_policy_checks check_ioc_reputation get_wazuh_agents get_agent_processes get_agent_ports get_top_security_threats search_cases create_case add_finding link_mitre save_report handoff_to_agent
metadata:
  category: detection
  display_name: Threat Hunting
  standards: [mitre-attack, nist-csf-2, sigma]
  version: "1.1"
---
# Threat Hunting

Hunting assumes the attacker got past existing detections. NIST CSF 2.0 DE.CM / DE.AE —
continuous monitoring and analysis beyond alert-driven work.

## PEAK framework (Prepare → Execute → Act with Knowledge)

Three hunt types:
1. **Hypothesis-driven** — test a specific idea about attacker behaviour.
2. **Baseline** — characterize normal, then examine outliers (e.g. rare processes,
   rare parent-child pairs, rare outbound destinations).
3. **Model-assisted** — use analytics/aggregation (`analyze_alert_patterns`,
   `get_alerts_aggregated`) to surface anomalies for human-style review.

TaHiTI (Targeted Hunting integrating Threat Intelligence) adds: start hunts from current
threat intel, and feed results back into intel and detection.

## Hypothesis template

```
Hypothesis: <actor behaviour> is occurring on <scope> and would appear as <observable> in <data source>.
ATT&CK: <technique id>
Data: <Wazuh rule groups / fields>
Time range: <e.g. 14d>
Success criteria: <what confirms / refutes>
```

Example: "An attacker has established persistence via cron on Linux servers; this would
appear as FIM or audit events on /etc/cron* or /var/spool/cron outside change windows
(T1053.003), last 14 days."

## Hunt catalog (starting points)

| Hunt | Technique | Query idea |
|---|---|---|
| Cron/systemd persistence | T1053.003, T1543.002 | FIM events (`rule_groups=["syscheck"]`, rules 550, 554) on cron/systemd paths, aggregated by host |
| New local accounts | T1136.001 | rule 5902 (useradd) and rule 60109 (Event ID 4720) outside provisioning systems |
| Log clearing | T1070.001/.002 | Event ID 1102 / Event ID 104; FIM rule 553 or size drops on /var/log files |
| Encoded PowerShell | T1059.001, T1027 | Sysmon Event ID 1 / Event ID 4688 command lines containing `-enc` (`rule_groups=["sysmon_eid1_detections"]`); load `wazuh-windows-sysmon` |
| Rare outbound destinations | T1071 | aggregate firewall/proxy destinations, look at count = 1–2 |
| SSH key additions | T1098.004 | FIM (rules 550, 554) on `authorized_keys`, only if monitored; see `wazuh-fim-investigation` |
| Web shells | T1505.003 | FIM adds of script files in web roots |
| Password spraying (low and slow) | T1110.003 | auth failures (rules 5710, 5716, 60122) by source across ≥ 10 users over 7d; composite rules may never fire |

Pull data with `search_security_events(query=..., time_range="7d")` (`time_range` up to 30d)
and `get_wazuh_alerts(rule_groups=[...], timestamp_start="now-14d")` for targeted pulls,
and `get_alerts_aggregated` / `analyze_alert_patterns` for baselines. Load
`wazuh-mcp-querying` for query limits and result formats. (`threat_hunt` on the Wazuh MCP
Server is an MCP prompt template, not a callable tool.)

## Procedure

1. Write the hypothesis (template above).
2. Pull data; aggregate first, then drill into outliers (≤ 20 per hunt).
3. For each outlier: benign explanation? (admin activity, deployment tooling). If not,
   check the host (`get_agent_processes`, `get_agent_ports`).
4. Decide outcome.

## Outcomes

| Outcome | Action |
|---|---|
| Confirmed malicious | `search_cases` then `create_case` (or attach); hand off to `triage`/`investigation` |
| Suspicious, unresolved | record, schedule follow-up hunt |
| Refuted | record; valuable negative result |
| Detection gap found | hand off to `detection-engineer` with the query and examples |

## Output

- `add_finding` (on a case) or `save_report(kind="hunt", ...)` titled `Hunt: <name>` with
  hypothesis, data and range, method, outliers reviewed, outcome, detection
  recommendations, and ATT&CK coverage. standard_refs: `NIST-CSF-2:DE.CM`.
- `link_mitre` on any case created.
