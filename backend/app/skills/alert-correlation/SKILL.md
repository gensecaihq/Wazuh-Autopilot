---
name: alert-correlation
description: Find related Wazuh activity around a case by time window and entity pivots, detect kill-chain progression and campaigns across hosts; use after triage when a case needs its surrounding context.
allowed-tools: get_case search_security_events get_wazuh_alerts analyze_alert_patterns get_alerts_aggregated get_wazuh_alert_summary get_wazuh_rules_summary search_cases update_case add_entities add_finding link_mitre handoff_to_agent
metadata:
  category: detection
  display_name: Alert Correlation
  standards: [nist-800-61r3, nist-csf-2, mitre-attack]
  version: "1.1"
---
# Alert Correlation

Goal: answer "is this isolated, or part of something bigger?" NIST CSF 2.0 DE.AE —
correlating adverse events from multiple sources.

## Procedure

1. `get_case` — collect entities (IPs, users, hosts, hashes) and first/last alert time.
2. Pick a window: default ±24h around the case; widen to 7d for slow activity
   (password spraying, beaconing) or narrow to ±1h for bursts.
3. Pivot on each attacker/victim entity (max 10 pivots per run — prioritize attacker IPs,
   then targeted users, then hosts).
4. Aggregate to find patterns rather than reading raw alerts one by one.
5. Classify the result (table below) and record it.

## Query patterns

| Question | Tool and arguments |
|---|---|
| Everything this IP did | `search_security_events(query="<ip>", srcip="<ip>", time_range="24h")` (`time_range` is one of 1h, 6h, 12h, 1d, 24h, 7d, 30d) |
| Alerts on the same host | `get_wazuh_alerts(agent_id="<id>", timestamp_start="now-24h", level="5")` (level means "this or higher"; `"10+"` also works) |
| Which rules and agents dominate | `get_alerts_aggregated(timestamp_start="now-24h", top_rules=20, top_agents=20)`. It aggregates by rule and agent, not by source IP; for per-IP counts use `search_security_events` with `srcip` |
| Rules or groups over a period | `get_wazuh_alert_summary(time_range="24h", group_by="rule.id")` (`group_by`: rule.level, rule.id, rule.groups, agent.id, agent.name) |
| Burst / trend / anomaly | `analyze_alert_patterns(time_range="24h", min_frequency=5)` |
| Group-wide auth failures | `get_wazuh_alerts(rule_groups=["authentication_failed", "authentication_failures"], timestamp_start="now-24h")` (single-failure and composite brute-force groups) |
| What a rule id means | `get_wazuh_rules_summary`, or load `wazuh-rules-and-decoders` |

Results come back as `"<Label>:\n{json}"` with items under `data.affected_items`. Keep
`compact=true` (the default), keep `limit` ≤ 500 per query, and narrow by time or agent
rather than paging through thousands of alerts. Load `wazuh-mcp-querying` for more.

## Correlation signals

- **Same source, many targets** → scanning / spraying / worm-like spread.
- **Many sources, same target** → distributed brute force / DDoS-like.
- **Same user, many hosts in short time** → lateral movement or credential reuse.
- **Tactic progression on one entity** (Recon → Initial Access → Execution → Persistence
  → Privilege Escalation → Lateral Movement) → active intrusion; raise severity.
- **Same hash / domain across hosts** → campaign or malware spread.
- **Periodic identical events** (fixed interval) → beaconing or scheduled task.

## Classification

| Result | Meaning | Action |
|---|---|---|
| isolated | No related activity beyond the case | keep severity; → response-planner if malicious, else resolve |
| related | Related alerts found on same entities | attach alerts/entities; → investigation if confidence < 0.7 |
| progression | Multiple tactics on same entity chain | raise severity per `severity-scoring`; → investigation |
| campaign | Same TTP/IOC across ≥ 3 hosts | raise to high/critical; → investigation + threat-intel |

Merge rather than duplicate: if `search_cases` finds another open case with the same
entities, reference it in your finding so a human can merge.

## Output

- `add_entities` for newly discovered related entities (validated).
- `link_mitre` for newly observed techniques.
- `update_case` severity/confidence if changed.
- `add_finding` titled `Correlation results`: window used, pivots run, classification,
  related alert counts per entity, related case ids. standard_refs: `NIST-CSF-2:DE.AE`.
