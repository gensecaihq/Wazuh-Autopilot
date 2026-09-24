---
name: severity-scoring
description: Compute a defensible priority (P1–P4), severity and confidence for a case from rule level, asset criticality, blast radius and ATT&CK tactic; use whenever you set or change case severity.
allowed-tools: get_case get_wazuh_agents get_wazuh_rules_summary perform_risk_assessment update_case add_finding
metadata:
  category: detection
  display_name: Severity Scoring
  standards: [nist-800-61r3, nist-csf-2, mitre-attack]
  version: "1.1"
---
# Severity Scoring

Severity must be explainable. Use this formula, then sanity-check it.

## Inputs (each scored 0–10)

| Factor | Weight | How to score |
|---|---|---|
| Rule level (L) | 0.30 | `min(10, rule.level * 10 / 15)` using the highest level in the case (see note below) |
| Asset criticality (A) | 0.25 | 10 crown-jewel / domain controller / prod DB; 7 prod server; 4 internal workstation; 2 lab/test |
| Tactic weight (T) | 0.20 | see table below, highest tactic present |
| Blast radius (B) | 0.15 | 1 host = 2; 2–5 hosts = 5; >5 hosts or domain-wide identity = 9; org-wide = 10 |
| Evidence strength (E) | 0.10 | 10 confirmed success (e.g. login after brute force, file dropped); 5 attempt; 2 anomaly only |

`score = 0.30L + 0.25A + 0.20T + 0.15B + 0.10E`

### About Wazuh levels

Wazuh levels describe the rule, not your environment. Some are misleading in context:
- High-level rules can be environmental or operational. For example, rule 204 (agent event queue
  flooded, level 12) is a pipeline problem, and rule 1003 (oversized syslog message,
  level 13) is often a misbehaving device. Keep L from the level, but score E low unless
  there is attacker evidence.
- Low-level rules can be the key evidence. For example, rule 5715 (sshd authentication success,
  level 3) right after rule 5712 (brute force, level 10) from the same source is a likely
  compromise. Score E = 10 and use the highest level in the case, not the success event's.
- Vulnerability-detector levels follow CVE severity (rules 23503, 23504, 23505, 23506 =
  Low, Medium, High, Critical). That is exposure, not activity: route to
  `vulnerability-prioritization` instead of scoring it as an intrusion.

## Tactic weights (MITRE ATT&CK)

| Tactic | Weight |
|---|---|
| Reconnaissance, Resource Development | 2 |
| Initial Access (attempt), Discovery | 4 |
| Execution, Persistence, Defense Evasion | 6 |
| Credential Access, Privilege Escalation | 7 |
| Lateral Movement, Command and Control | 8 |
| Collection, Exfiltration | 9 |
| Impact | 10 |

## Mapping

| Score | Priority | Severity | Target response |
|---|---|---|---|
| ≥ 8.0 | P1 | critical | immediate, page on-call |
| 6.0–7.9 | P2 | high | within 1 hour |
| 4.0–5.9 | P3 | medium | same business day |
| < 4.0 | P4 | low / informational | backlog / batch |

Overrides (apply after the formula):
- Confirmed data exfiltration or ransomware behaviour → P1 regardless.
- Only reconnaissance with no success, external source → cap at P3.
- Asset tagged protected/critical in org context → floor at P2.

## Confidence (0–1)

Confidence is how sure you are the activity is malicious, separate from severity.

| Evidence | Confidence |
|---|---|
| Multiple independent signals + threat-intel match | 0.9–1.0 |
| Clear pattern (e.g. brute force then success) | 0.75–0.9 |
| Single high-fidelity rule | 0.6–0.75 |
| Single generic rule / anomaly | 0.3–0.6 |
| Likely benign, unexplained | < 0.3 |

`perform_risk_assessment` may be used as an extra input; don't let it override your own
reasoning without explanation.

## Output

- `update_case(case_id, severity=..., confidence=...)`.
- `add_finding` titled `Severity rationale` containing the factor table with scores,
  the computed score, overrides applied, priority, and confidence reasoning.
  standard_refs: `NIST-800-61r3`.
