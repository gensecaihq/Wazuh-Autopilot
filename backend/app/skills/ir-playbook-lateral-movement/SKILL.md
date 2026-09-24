---
name: ir-playbook-lateral-movement
description: Incident-response playbook for lateral movement — SMB/admin shares, WinRM/PowerShell remoting, RDP, SSH, PsExec/WMI remote execution, pass-the-hash and remote services/tasks; use when Wazuh shows internal-to-internal authentication or remote-execution chains (e.g. rules 92652, 92653, 92650, 92068, 91823, or SSH success rule 5715 from an internal source).
allowed-tools: get_wazuh_alerts search_security_events get_wazuh_agents check_agent_health get_agent_processes get_agent_ports get_case search_cases update_case add_entities link_mitre add_finding list_actions wazuh_check_agent_isolation wazuh_check_user_status wazuh_check_process wazuh_check_blocked_ip
metadata:
  category: response
  display_name: IR Playbook — Lateral Movement
  standards: [nist-800-61r3, sans-picerl, mitre-attack, mitre-d3fend, nist-csf-2, cis-v8-1, nist-800-53r5]
  version: "2.1"
---
# IR Playbook — Lateral Movement

Severity **critical**: lateral movement means an adversary already has a foothold and valid credentials.
Correlate across hosts before containment. Rule IDs are from the stock Wazuh 4.14 ruleset (levels official);
several need Sysmon or PowerShell script-block logging on the endpoints. Full procedure: `references/playbook.md`.

## 1. Detection signals

| Technique | Wazuh rules (level) | Needs |
|---|---|---|
| T1550.002 Pass-the-hash (NTLM remote logon) | rules 92652 (L6), 92657 (L6, NTLM + RDP) | Security log, Event ID 4624 logon type 3/10 |
| T1021.001 RDP | rule 92653 (L3, RDP logon), rule 92656 (L15, RDP from loopback — tunnelling) | Security log |
| T1021.002 SMB / admin shares | rules 92105 (L3), 92106 (L3); rule 92650 (L12, service binary in Windows root — dropped via admin share); rules 92202, 92218 (L6, executable dropped in Windows root) | Sysmon Event ID 3 / 11 |
| T1569.002 PsExec / remote service | rule 92068 (L3, PsExec execution); rule 61138 (L5, new service, Event ID 7045) | Sysmon Event ID 1, System log |
| T1021.006 WinRM / PS remoting | rule 92110 (L4, WinRM network activity); rule 91823 (L14, Invoke-Command on a remote computer); rule 92220 (L6, binary dropped by WinRM process) | Sysmon, PowerShell/Operational |
| T1047 WMI | rule 92070 (L6, WMI spawned PowerShell); rule 92071 (L12, WMI PowerShell with base64) | Sysmon Event ID 1 |
| T1053.005 Scheduled task | rule 60228 (L4, Event ID 4698) | Security log |
| T1003.001 Credential access before movement | rules 92900 (L12), 92403 (L12) — LSASS accessed | Sysmon Event ID 10 / 8 |
| T1021.004 SSH (Linux) | rule 5715 (L3, success) from an internal source after rules 5716, 5760 (L5) failures; rule 92603 (L6, file copied in via SCP); rule 92602 (L12, Impacket signature) | sshd logs, auditd |
| Account manipulation during spread | rules 60109 (L8, account created/enabled), 60154 (L12, Administrators group changed) | Security log |

High-confidence patterns: one account authenticating to ≥3 hosts within 10 min; workstation-to-workstation admin
logons; service accounts used interactively; logons outside the account's baseline. Wazuh has no stock rule for
the fan-out pattern — create it as `custom rule 100230` (frequency rule over group `authentication_success`,
`<same_field>dstuser</same_field>`, `<different_field>agent.id</different_field>`; validate with `wazuh-logtest`).
Explicit-credential logons (Event ID 4648) have no stock rule either; add `custom rule 100231` if you rely on them.

## 2. Triage / investigation (investigation agent)

1. Scope: `search_security_events` for the account and the source host across all agents (`time_range: "24h"`, then
   `"7d"`); `get_wazuh_alerts` with `rule_groups: ["authentication_success","sysmon_eid3_detections","sysmon_eid1_detections"]`
   on each suspected host. `search_cases` for the host/account first.
2. Answer:
   - Which account, which **source** host? Admin jump host (expected) or workstation?
   - How many destinations, over what window? Any domain controllers or crown-jewel servers?
   - Which technique (SMB, WinRM, RDP, WMI, PsExec, SSH)?
   - Initial compromise on the source (phishing, brute force, malware)? If brute force → `ir-playbook-bruteforce`.
3. On each touched host (DCs and servers first):
   - `get_agent_processes`: psexesvc, wmiprvse children, wsmprovhost, unusual powershell, credential tools.
   - `get_agent_ports`: new listeners, RDP/WinRM exposure, outbound C2.
   - `check_agent_health`: agents stopped or tampered with during the spread.
   - Hand off to threat-intel for hashes/external C2 reputation.
4. `add_entities` (account = compromised, source host, each destination host with `agent_id`), `link_mitre`,
   `update_case` severity critical unless proven sanctioned (change ticket, jump host, known admin).
5. `add_finding`: host-hop timeline, compromised accounts, confirmed/suspected hosts, first hop time, and a
   containment **recommendation to response-planner**.

## 3. Response (response-planner)

Check current state first (`wazuh_check_agent_isolation`, `wazuh_check_user_status`), then propose:

| Situation | Proposal |
|---|---|
| Source host confirmed compromised | `propose_action(type="isolate_host", target=<src id>, params={"agent_id": <src id>})` (D3-NI) |
| Compromised account active on a host | `propose_action(type="disable_user", params={"agent_id": <host>, "username": <account>})` (D3-AL) |
| Remote-execution tooling running | `propose_action(type="kill_process", params={"agent_id": <host>, "process_id": <pid>})` |
| External C2 seen from touched hosts | `propose_action(type="block_ip", params={"ip_address": <c2>, "all_agents": true})` |
| Destination hosts with confirmed attacker activity | `isolate_host` per host, ordered by criticality |

Sequencing: isolate the source before killing processes; disable accounts after isolation so the attacker can't
pivot during the change; never isolate domain controllers without a human decision (keep DCs in protected targets).
Domain-level account disable, krbtgt reset and GPO changes are human tasks — `add_finding` with owner and urgency.

## 4. Eradication and recovery

- Reset credentials for every account in the chain (krbtgt twice if Kerberos abuse is suspected).
- Remove persistence created during movement (services, scheduled tasks, WMI subscriptions — rules 89501, 89502 flag WMI consumers).
- Rebuild or clean isolated hosts; un-isolation is a human-approved rollback in the approvals UI.
- Tighten: LAPS, tiered admin model, block workstation-to-workstation SMB/RDP, restrict WinRM.

## 5. Verification

The responder verifies each executed action (`wazuh_check_agent_isolation`, `wazuh_check_user_status`,
`wazuh_check_process`) and records verification findings.

## 6. Evidence and records

- Findings with `standard_refs` such as `MITRE-ATTACK:T1021.002`, `MITRE-ATTACK:T1550.002`, `NIST-800-61r3:Respond`.
- Preserve references to Event IDs 4624, 4648, 4672, 7045 and 4698 before hosts are reimaged.
- Coverage gaps (no Sysmon, no script-block logging, no fan-out rule) → hand off to detection-engineer.
- Hand off to reporting for the incident report with blast radius and credential-reset status.

## Escalation

| Condition | Escalate to |
|---|---|
| Domain controller touched or domain admin used | IR lead + identity team (human) |
| > 10 hosts touched | Major incident process |
| Ransomware precursors (backup/VSS tampering) | `ir-playbook-ransomware` immediately |
