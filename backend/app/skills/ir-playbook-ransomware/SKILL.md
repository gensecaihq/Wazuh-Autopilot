---
name: ir-playbook-ransomware
description: Incident-response playbook for ransomware — mass file modification/encryption, ransom notes, shadow-copy and backup deletion, service stopping and log clearing; use when Wazuh shows FIM bursts (rules 550, 553, 554), antimalware detections (rules 62113, 87105), audit-log clearing (rule 60117) or recovery-inhibition commands. Containment within minutes.
allowed-tools: get_wazuh_alerts search_security_events get_wazuh_agents check_agent_health get_agent_processes get_agent_ports get_case search_cases update_case add_entities link_mitre add_finding list_actions wazuh_check_agent_isolation wazuh_check_process wazuh_check_file_quarantine wazuh_check_user_status wazuh_check_blocked_ip
metadata:
  category: response
  display_name: IR Playbook — Ransomware
  standards: [nist-800-61r3, sans-picerl, mitre-attack, mitre-d3fend, nist-csf-2, iso-27001-2022, cis-v8-1]
  version: "2.1"
---
# IR Playbook — Ransomware

Severity **critical**. Speed matters more than completeness: isolate within **5 minutes** of confirmation,
scope within **30 minutes**. MITRE ATT&CK: T1486 (encrypted for impact), T1490 (inhibit recovery),
T1489 (service stop), T1070.001 (log clearing), T1567 (pre-encryption exfil). Rule IDs are from the stock
Wazuh 4.14 ruleset (levels official). Full procedure and family indicators: `references/playbook.md`.

## 1. Detection signals

| Source | Signal | Wazuh rules (level) |
|---|---|---|
| FIM | Bulk changes / deletions / additions on monitored paths | rules 550 (L7, checksum changed), 553 (L7, file deleted), 554 (L5, file added); group `syscheck` |
| FIM (Windows registry) | Run keys / services changed | rules 594 (L5), 750 (L5), 752 (L5) |
| Antimalware | Defender detection / suspicious behaviour | rules 62113 (L14), 62122 (L12), 62123 (L12); Defender protection disabled: rules 92008 (L12), 92009 (L13), 92012 (L13, controlled folder access disabled) |
| VirusTotal integration | Dropped file flagged | rule 87105 (L12) |
| Sysmon file drops | Executable in malware-typical folders, Users\Public, Office-created payloads | rules 92213 (L15), 92207 (L12), 92214 (L15) |
| Sysmon network | Suspicious binary opened a network connection | rule 92104 (L15) |
| Log tampering | Security log cleared (Event ID 1102) | rule 60117 (L9); rule 63103 (L5) |
| Credential theft before encryption | LSASS / SAM access | rules 92900 (L12), 92024 (L14), 92026 (L14) |
| Rootkit / host anomaly | Rootcheck | rules 510 (L7), 521 (L11, possible kernel-level rootkit) |
| Microsoft Graph (if integrated) | Defender for Endpoint ransomware alert | rules 99535 (L12), 99594 (L15) |

Stock gaps — the org must create these (range 100000–120000, validate with `wazuh-logtest`):
- Mass FIM burst: `custom rule 100401` — frequency ≥ 100 over group `syscheck` in 60 s, `<same_field>agent.id</same_field>`.
- Ransom-note / encrypted-extension creation: `custom rule 100402` — `syscheck.path` matching note names
  (`README*.txt`, `*DECRYPT*`, `*RESTORE*`) or known extensions.
- Recovery inhibition: `custom rule 100403` — Sysmon Event ID 1 `commandLine` matching `vssadmin.*delete shadows`,
  `wmic shadowcopy delete`, `bcdedit.*recoveryenabled no`, `wbadmin delete catalog`. The stock ruleset has no rule
  for these commands; treat them as critical.
- Backup / VSS service stopped: `custom rule 100404` on System-log Event ID 7036/7040 for VSS and backup agents.

Treat any ransom note as confirmation. Mass FIM changes from a known backup/sync/deployment job → confirm with
the owner before acting and tune the rule.

## 2. Triage / investigation (investigation agent, ≤ 5 minutes)

1. `get_wazuh_alerts` for the host (`agent_id`, `timestamp_start: "now-1h"`, `rule_groups: ["syscheck","windows_defender","sysmon_eid11_detections"]`);
   `search_cases` — part of an open incident?
2. Answer fast: encryption **active** (FIM volume still rising)? Which hosts? Ransom note? Recovery inhibition
   seen? Which account runs the encrypting process (`get_agent_processes`)?
3. `add_entities` (hosts with `agent_id`, account, process, note/file paths, external IPs), `link_mitre`
   T1486/T1490, `update_case` severity critical.
4. If encryption is active, `add_finding` with an **immediate containment recommendation to response-planner**
   (host, process id, file path) — skip deep correlation until containment is proposed.
5. Then scope (≤ 30 min): `search_security_events` for the same hash/process/FIM bursts fleet-wide; agents that went
   silent (`get_wazuh_agents` with `status: "disconnected"`, `check_agent_health`); neighbours of patient zero with
   `get_agent_processes` / `get_agent_ports` for lateral-movement precursors (PsExec, WMI, RDP) and pre-encryption
   exfil (rclone, large uploads). Hand off to threat-intel for family/TTPs and IOC reputation, and run
   `ir-playbook-lateral-movement` / `ir-playbook-data-exfiltration` in parallel where indicated.

## 3. Response (response-planner)

| Situation | Proposal |
|---|---|
| Encryption active on a host | `propose_action(type="isolate_host", target=<id>, params={"agent_id": <id>})` with confidence ≥ 0.9 — first action |
| Encrypting process identified | `propose_action(type="kill_process", params={"agent_id": <id>, "process_id": <pid>})` |
| Ransomware binary on disk | `propose_action(type="quarantine_file", params={"agent_id": <id>, "file_path": <path>})` |
| Account used to spread | `propose_action(type="disable_user", params={"agent_id": <id>, "username": <user>})` |
| C2 / exfil destinations | `propose_action(type="block_ip", params={"ip_address": <ip>, "all_agents": true})` |

Isolation defaults to supervised; flag urgency in the rationale so approvers act within minutes. Check
`wazuh_check_agent_isolation` before re-proposing. Do **not** propose restarting encrypted hosts (memory evidence
and keys can be lost). Segmentation beyond Wazuh active response, backup lockdown and domain account resets are
human tasks — record them with `add_finding` and owners.

## 4. Eradication and recovery

- Rebuild affected hosts; restore from offline/immutable backups verified clean.
- Reset credentials domain-wide if domain accounts were used; hunt persistence before reconnecting.
- Un-isolate only after verification and owner sign-off (rollback in the approvals UI).
- No payment or actor contact without an executive/legal decision (record in findings only).

## 5. Verification

The responder verifies each executed action (`wazuh_check_agent_isolation`, `wazuh_check_process`,
`wazuh_check_file_quarantine`, `wazuh_check_user_status`, `wazuh_check_blocked_ip`).

## 6. Evidence and records

- Preserve ransom notes, sample encrypted files, binary hashes, process trees (ISO 27001 A.5.28).
- Findings with `standard_refs`: `MITRE-ATTACK:T1486`, `MITRE-ATTACK:T1490`, `NIST-800-61r3:Respond`,
  `SANS-PICERL:Containment`, `NIST-CSF-2:RS.MI`.
- Hand off to reporting for the executive BLUF and incident report; hand off to detection-engineer for the
  custom rules above if they are missing.

## Escalation

| Condition | Escalate to |
|---|---|
| Any confirmed ransomware | IR lead, CISO, incident commander (human) immediately |
| Multiple hosts or servers encrypted | Major-incident process, legal, cyber-insurance contact |
| Data exfiltration evidence | `ir-playbook-data-exfiltration` in parallel |
