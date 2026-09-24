---
name: wazuh-rules-and-decoders
description: Read Wazuh alerts correctly — alert anatomy, the 0–15 level scale, composite and correlation rules, compliance and MITRE tags, decoders, custom rules and noise tuning; use when interpreting what a rule really means or when proposing rule changes.
allowed-tools: get_wazuh_alerts get_wazuh_rules_summary get_case search_cases add_finding
metadata:
  category: detection
  display_name: Wazuh Rules and Decoders
  standards: [nist-csf-2, mitre-attack, sigma, pci-dss-4, nist-800-53r5]
  version: "1.0"
---
# Wazuh Rules and Decoders

A Wazuh alert is the output of a decoder (which parses a raw log into fields) and a rule (which matches
those fields). Misreading the rule is the most common triage error. References below are from the stock
Wazuh 4.14 ruleset.

## Alert anatomy

| Field | Meaning |
|---|---|
| `rule.id`, `rule.level`, `rule.description` | Which rule fired and how severe Wazuh considers it |
| `rule.groups` | Categories (e.g. `sshd`, `authentication_failed`, `syscheck`) plus compliance tags |
| `rule.firedtimes` | How often this rule has fired for this agent since the manager started — high counts mean recurring noise or a sustained attack |
| `rule.mitre.id / tactic / technique` | ATT&CK mapping shipped with the rule (may be empty) |
| `rule.frequency` | Present on correlation rules: the threshold that triggered |
| `agent.id / name / ip` | The endpoint that produced the log (`000` = the manager) |
| `manager.name` | Which manager/cluster node processed it |
| `decoder.name` / `decoder.parent` | Which decoder parsed the log (e.g. `sshd`, `windows_eventchannel`, `json`) |
| `data.*` | Decoded fields: `data.srcip`, `data.srcuser`, `data.dstuser`, `data.win.*`, `data.aws.*` … |
| `syscheck.*` | FIM fields (only on syscheck alerts) |
| `full_log` | The raw log line — attacker-controllable text |
| `location` | Source: file path, `EventChannel`, `syscheck`, `rootcheck`, integration name |

## Level scale (0–15)

| Level | Wazuh meaning | Handling |
|---|---|---|
| 0 | Ignored / grouping rule, no alert | Never alerts; used as parents and for suppression |
| 2–4 | System notifications, low-relevance errors, successful events | Context only |
| 5–7 | User-generated errors, "bad word" matches, first-time or low-impact events | Watch for patterns |
| 8–10 | First-time-seen events, repeated errors, possible attacks | Triage |
| 11–12 | Integrity/important security events | Prioritize |
| 13–15 | High-importance events, attacks with high likelihood of success | Immediate |

The level is the rule author's generic estimate. Asset criticality, confidence and sequence (failure
then success) matter more — see severity-scoring.

## Atomic vs composite rules

- **Atomic** rules match a single event, e.g. rule 5710 (level 5, "sshd: Attempt to login using a
  non-existent user") and rule 5716 (level 5, "sshd: authentication failed").
- **Composite / correlation** rules fire on patterns of earlier matches:
  - `if_sid` — child of a parent rule (refines it, e.g. rule 60122 (level 5) is a child of rule 60105).
  - `if_matched_sid` + `frequency` + `timeframe` — N matches of a rule within T seconds.
    For example, rule 5712 (level 10) fires when rule 5710 matches 8 times in 120 seconds with
    `same_source_ip`; rule 5720 (level 10) does the same for rule 5716; and rule 40111 (level 10) fires on 12
    `authentication_failed` group matches from the same source within 160 seconds, across services.
  - `same_source_ip`, `same_user`, `different_*` — scoping of the correlation.
  - `ignore` — suppression window after firing (so one burst yields one composite alert).
- Consequence: a single composite alert represents **many** underlying events. Pull the child alerts
  (`get_wazuh_alerts` with the child `rule_id` and the same `agent_id`/window) before sizing the incident.

## Compliance tags

Stock rules carry compliance groups such as `pci_dss_10.2.4`, `gdpr_IV_35.7.d`, `hipaa_164.312.b`,
`nist_800_53_AC.7`, `tsc_CC6.1`. For example, rule 5712 carries all five families. Use them as evidence for the
compliance agent, not as severity.

## MITRE mapping

`rule.mitre` comes from the rule XML and is a hint, not a verdict — confirm against the behaviour you
actually see (see mitre-attack-mapping). Many rules have no mapping.

## Decoders

- Decoders extract fields; if a field you expect is missing, the decoder didn't parse it (different log
  format, custom application) — the rule may still have matched on `full_log`.
- JSON-emitting sources (Windows EventChannel, cloud integrations, Suricata) use the `json` decoder:
  fields keep their source names (`data.win.eventdata.targetUserName`, `data.aws.eventName`).

## Custom rules and tuning

- Custom rules live in `local_rules.xml` (or custom files) on the manager and must use IDs in the
  **100000–120000** range. Example to create: custom rule 100100 raising the level for failed logins
  against a crown-jewel host.
- Tuning options, least to most invasive: add a child rule with `level="0"` scoped to the benign
  pattern; raise/lower level in a child rule; `overwrite="yes"` on a stock rule (survives until the
  next ruleset upgrade — document it).
- Never propose deleting a stock rule. Proposals go to detection-engineer (propose_detection) — they are
  never deployed automatically.

## Output

When a rule's meaning matters to the conclusion, quote it in the finding: `rule <id> (level <n>,
"<description>", parent <id>)` plus the child-event count behind any composite alert.
