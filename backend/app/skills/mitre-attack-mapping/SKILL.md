---
name: mitre-attack-mapping
description: Map Wazuh alerts and observed behaviour to MITRE ATT&CK techniques and tactics and record them on the case; use whenever you identify attacker behaviour or see rule.mitre data.
allowed-tools: get_case get_wazuh_alerts search_security_events get_wazuh_rules_summary link_mitre add_finding
metadata:
  category: detection
  display_name: MITRE ATT&CK Mapping
  standards: [mitre-attack, nist-csf-2]
  version: "1.1"
---
# MITRE ATT&CK Mapping

ATT&CK is the shared language between triage, hunting, response and detection
engineering. Map precisely: prefer a sub-technique when evidence supports it, otherwise
the parent technique.

## Procedure

1. Start with `rule.mitre.id` / `rule.mitre.tactic` from each alert — Wazuh ships these
   on many rules. Treat them as a hint, not truth: verify against the behaviour.
2. Add techniques for behaviour seen in logs that the rule didn't tag (e.g. a process
   command line showing discovery commands).
3. Pick the tactic from the context: the same technique can serve multiple tactics
   (T1078 Valid Accounts: Initial Access, Persistence, Privilege Escalation, Defense
   Evasion) — record the tactic that fits this case.
4. Assign a numeric confidence per technique: 0.9 confirmed (log evidence of the
   behaviour), 0.7 likely (strong indicator), 0.4 possible (rule tag only).

## Wazuh rule → technique mappings

The first column is taken from the Wazuh 4.14 ruleset's own `<mitre>` tags. The ruleset
is not always right: rule 60122 (Windows logon failure, level 5) is tagged T1531 Account
Access Removal, which one failed logon isn't. Treat every tag as a hint.

| Wazuh signal | Ruleset tag | Map to (when behaviour confirms) |
|---|---|---|
| rule 5710 sshd non-existent user (level 5) | T1110.001, T1021.004 | T1110.001 Password Guessing |
| rules 5712, 5720, 5763 sshd brute force / multiple failures (level 10); rule 5716 single failure | T1110 | T1110.001, or T1110.003 Password Spraying if many users from one source |
| rule 5715 sshd authentication success | T1078, T1021 | T1078 Valid Accounts only after failures or from an unusual source; T1021.004 SSH for internal hops |
| rule 60204 multiple Windows logon failures (level 10) | T1110 | T1110 (Event ID 4625 bursts) |
| rule 60106 Windows logon success | T1078 | T1078; Event ID 4624 logon type 10 between workstations suggests T1021.001 RDP |
| rule 550 FIM checksum changed | T1565.001 | T1505.003 Web Shell if a script changed in a web root; T1543.002 / T1053.003 for systemd units or cron files |
| rule 553 FIM file deleted | T1070.004, T1485 | T1070.004 Indicator Removal if logs or tools were deleted |
| rule 554 FIM file added | (none) | T1105 Ingress Tool Transfer if a binary or script appeared in a temp or web path |
| rules 594, 750 registry value/key changed | T1565.001, T1112 | T1547.001 Run Keys when under `...\CurrentVersion\Run` |
| rule 5902 new user added | T1136 | T1136.001 Create Account: Local Account |
| rule 5402 sudo to root; rule 5401 failed sudo | T1548.003 | T1548.003 Sudo and Sudo Caching |
| rule 60154 Administrators group changed (level 12) | T1484 | T1098 Account Manipulation / T1078.002 if a domain account was added |
| rule 504 agent disconnected, rule 506 agent stopped | T1562.001 | T1562.001 Impair Defenses only with corroboration (many agents, attacker activity) |
| rule 87105 VirusTotal positives (level 12) | T1203 | map to what the file does (e.g. T1496 for a miner); T1203 only for exploit documents |
| rule 92213 Sysmon: executable dropped in a malware-typical folder (level 15) | T1105 | T1105 Ingress Tool Transfer |
| rule 510 rootcheck anomaly | (none) | T1014 Rootkit / T1036 Masquerading only when the finding describes a hidden process or trojaned binary |
| web attack rules (`rule.groups` `web`, `attack`) | varies | T1190 Exploit Public-Facing Application |
| Windows Event ID 1102 / 104 log cleared | varies | T1070.001 Clear Windows Event Logs |
| Sysmon Event ID 1 with `powershell -enc` | varies | T1059.001 PowerShell + T1027 Obfuscated Files or Information |
| beaconing / outbound to known-bad IP | none | T1071 Application Layer Protocol |

Look up the tags for any rule with `get_wazuh_rules_summary`. Load
`wazuh-rules-and-decoders` for how `rule.mitre` is populated, and `wazuh-windows-sysmon`
for Windows/Sysmon specifics.

## Tactic ordering (for progression analysis)

Reconnaissance → Resource Development → Initial Access → Execution → Persistence →
Privilege Escalation → Defense Evasion → Credential Access → Discovery → Lateral
Movement → Collection → Command and Control → Exfiltration → Impact.

## Technique record

```json
{"technique_id": "T1110.001", "name": "Password Guessing", "tactic": "Credential Access",
 "confidence": 0.9, "evidence": "38 sshd failures (rule 5716) then rule 5712 from 203.0.113.7 in 10 min"}
```

## Output

- `link_mitre(case_id, techniques)` with the records above.
- `add_finding` titled `ATT&CK mapping` when you add techniques beyond the rule tags,
  including the evidence for each. standard_refs: `MITRE-ATTACK:<technique_id>`.
