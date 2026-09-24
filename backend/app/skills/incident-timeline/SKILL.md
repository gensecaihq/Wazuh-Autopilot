---
name: incident-timeline
description: Build an ordered, evidence-linked incident timeline with first/last seen, dwell time and pivot points; use when a case spans multiple alerts, hosts or stages and needs a clear narrative.
allowed-tools: get_case get_wazuh_alerts search_security_events get_alerts_aggregated get_wazuh_agents add_finding update_case handoff_to_agent
metadata:
  category: investigation
  display_name: Incident Timeline
  standards: [nist-800-61r3, sans-picerl, mitre-attack]
  version: "1.1"
---
# Incident Timeline

A timeline turns a pile of alerts into a story a responder or executive can act on.
NIST SP 800-61r3 expects incident documentation of what happened, when, and how it was
detected; the timeline is the backbone of that record.

## Procedure

1. `get_case` — gather attached alerts, entities, findings, actions.
2. Pull supporting events for the key entities over the incident window
   (`search_security_events`, `get_wazuh_alerts` filtered by agent/user/ip).
3. Normalize every timestamp to UTC ISO 8601. A Wazuh alert's `timestamp` is when the
   manager processed the event. The original event time is in the log itself
   (`predecoder.timestamp`, or the time at the start of `full_log`, or
   `data.win.system.systemTime` for Windows). Use the event time when they differ by more
   than a few seconds, and note clock skew or delayed delivery (e.g. an agent reconnecting
   and flushing its buffer).
4. Order events; collapse repetitive ones ("38 sshd failures 09:02–09:12"). Wazuh
   composite rules summarize bursts: one rule 5763 or rule 5712 alert stands for several
   single failures (rules 5716, 5760, 5710), so count the underlying failures, not the
   composites.
5. Label each event with an ATT&CK tactic where possible.
6. Identify the key milestones and gaps.

## Milestones to identify

| Milestone | Definition |
|---|---|
| First malicious activity | Earliest event attributable to the attacker (may predate the first alert) |
| Initial access | First successful foothold (login success, exploit, execution) |
| First detection | Timestamp of the first Wazuh alert on this activity |
| Escalation / spread | Privilege gain, new host touched |
| Containment | Time an approved action was executed and verified |
| Last activity | Latest attacker event |

Derived metrics:
- **Dwell time** = first detection − first malicious activity.
- **Time to contain** = containment − first detection.
- **Active duration** = last activity − first malicious activity.

## Pivot points

Mark events where the investigation should branch: a new host, a new account, a new
external IP, a dropped file hash. Each pivot is a question for correlation or
investigation ("what else did account X do after 10:14?").

## Gaps

Explicitly list periods with no telemetry. Absence of evidence is not evidence of
absence, so say so. Check `get_wazuh_alerts` for the host's agent-lifecycle and flooding
alerts in the window: rule 504 (agent disconnected), rule 506 (agent stopped), rule 503
(agent started), rule 203 (event queue full, events may be lost), rule 204 (queue
flooded). `get_wazuh_agents` shows the current status and last keepalive. For
manager-side log-collection or cluster problems, hand off to `platform-engineer`. A stop
or disconnect right before attacker activity is itself suspicious (T1562.001).

## Timeline format

```
| Time (UTC) | Host / Entity | Event | Tactic | Source |
|---|---|---|---|---|
| 2026-03-24 09:02–09:12 | 203.0.113.7 → web-01 | 38 SSH auth failures (root, admin) | Credential Access | rules 5716, 5760 x38; rule 5763 x4 |
| 2026-03-24 09:13:05 | web-01 / admin | SSH login success | Initial Access | rule 5715 |
```

Cite the alert/rule id for every row. Keep to ≤ 40 rows; summarize the rest.

## Output

- `add_finding` titled `Incident timeline` containing the table, milestones, derived
  metrics, pivots and telemetry gaps. standard_refs: `NIST-800-61r3`, `SANS-PICERL`.
- `update_case(summary=...)` with a 2–3 sentence narrative if the summary is stale.
