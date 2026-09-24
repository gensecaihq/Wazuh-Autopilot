---
name: ir-playbook-bruteforce
description: Incident-response playbook (PB-001) for brute-force, password-spraying and credential-stuffing attacks against SSH, PAM, Windows logon and web logins; use when Wazuh raises authentication-failure bursts (rule group authentication_failures, e.g. rules 5712, 5763, 60204) or a failure burst followed by a success (rule 40112).
allowed-tools: get_wazuh_alerts search_security_events get_wazuh_agents check_agent_health get_agent_processes get_agent_ports get_case search_cases update_case add_entities link_mitre add_finding list_actions wazuh_check_blocked_ip wazuh_check_user_status
metadata:
  category: response
  display_name: IR Playbook — Brute Force
  standards: [nist-800-61r3, sans-picerl, mitre-attack, mitre-d3fend, nist-csf-2, cis-v8-1, pci-dss-4]
  version: "2.1"
---
# IR Playbook — Brute Force (PB-001)

Semi-automated: the swarm detects, investigates and proposes; the autonomy policy and the approvals
queue decide what executes. Default severity **high**, **critical** once a login succeeds.
MITRE ATT&CK T1110 (.001 Password Guessing, .003 Password Spraying, .004 Credential Stuffing).
Rule IDs below are from the stock Wazuh 4.14 ruleset; levels are the official ones.
Full procedure: `references/playbook.md`.

## 1. Detection signals

| Signal | Wazuh rules (level) | Notes |
|---|---|---|
| SSH single failures | rules 5710 (L5, non-existent user), 5716 (L5), 5760 (L5) | group `authentication_failed` |
| SSH brute force (composite) | rules 5712 (L10, non-existent users), 5763 (L10, auth failed), 5720 (L10), 5758 (L8, max attempts exceeded) | group `authentication_failures` |
| PAM / syslog repeated failures | rules 5503 (L5), 5551 (L10), 2502 (L10) | Linux console/su/other PAM services |
| Windows logon failures (Event ID 4625) | rules 60122 (L5), 60204 (L10, multiple failures) | eventchannel, group `windows_security` |
| Windows account lockout (Event ID 4740) | rule 60115 (L9) | lockouts across many accounts = spraying |
| Any source, many failures (cross-decoder) | rule 40111 (L10) | frequency rule on group `authentication_failed`, same source IP |
| **Failures followed by a success** | rule 40112 (L12) | same source IP within 240 s — **escalate to critical** |
| Success events to check | rules 5715 (L3, sshd success), 60106 (L3, Event ID 4624) | correlate with the failing source |
| Web / CMS logins | rule 31510 (L8, WordPress/Joomla brute force); rule 31151 (L10, many HTTP 400s) | other web apps need custom rules |

Stock gaps (create as custom rules, range 100000–120000):
- Password spraying (one source, ≥10 distinct accounts, few attempts each) — e.g. `custom rule 100210`:
  `<rule id="100210" level="10" frequency="10" timeframe="1800"><if_matched_group>authentication_failed</if_matched_group><same_source_ip /><different_field>dstuser</different_field>…`
- Credential stuffing (one account, many sources) — `custom rule 100211` using `<same_field>dstuser</same_field>`
  with `<different_srcip />`.
- VPN / cloud / API logins not covered by an installed decoder.
- Validate custom rule syntax against your manager version (`wazuh-logtest`) before deploying.

## 2. Triage / investigation (investigation agent)

1. Pull context: `get_wazuh_alerts` (`agent_id`, `rule_groups: ["authentication_failed","authentication_failures"]`,
   `timestamp_start: "now-6h"`, `compact: true`) and `search_security_events`
   (`query: "authentication"`, `srcip: <ip>`, `time_range: "24h"`) across the fleet. `search_cases` on the
   source IP before creating anything; case creation belongs to triage.
2. Answer:
   - Single source or distributed? Internal or external? External IPs → hand off to threat-intel for reputation.
   - One account (guessing) or many (spraying)? Privileged accounts targeted (root, Administrator, svc_*)?
   - **Did any attempt succeed?** Look for rule 40112, or rules 5715, 60106 from the same source after the failures.
   - Internet-facing target? (`get_wazuh_agents` → groups, IP)
3. `add_entities` (source IP = attacker, host = victim with `agent_id` in enrichment, targeted users = victim),
   `link_mitre` T1110.x, `update_case` severity (failures only → high; success → critical).
4. Only if a login succeeded or the source is internal: `get_agent_processes` / `get_agent_ports` on the target
   (new shells, reverse connections, miners); check post-login activity — sudo to root (rule 5402, L3),
   new users (rule 5902, L8), root crontab changes (rule 2833, L8), SSH keys added (FIM on `authorized_keys`,
   rules 550, 554). Internal source → hand off to lateral-movement analysis.
5. `add_finding` with the evidence and a containment **recommendation to response-planner** (target IP,
   agent_id, affected users, whether a login succeeded).

## 3. Response (response-planner)

Propose, never execute. Include confidence and a rationale with rollback in every call. Check current state
first with `wazuh_check_blocked_ip` so you don't propose a duplicate block.

| Situation | Proposal |
|---|---|
| External source, failures only | `propose_action(type="block_ip", target=<ip>, params={"ip_address": <ip>, "agent_id": <target agent>})` — low risk, reversible (D3-ITF) |
| Same source hitting many hosts | `block_ip` with `params={"ip_address": <ip>, "all_agents": true}` — say "fleet-wide" in the rationale |
| Linux SSH target, per-host deny | `propose_action(type="host_deny", params={"agent_id": <id>, "ip_address": <ip>})` |
| Firewall drop on one host | `propose_action(type="firewall_drop", params={"agent_id": <id>, "ip_address": <ip>})` |
| **Login succeeded** with an attacked account | `propose_action(type="disable_user", target=<user>, params={"agent_id": <id>, "username": <user>})` (D3-AL, high risk → supervised) |
| Hands-on-keyboard after login | `propose_action(type="isolate_host", target=<id>, params={"agent_id": <id>})` (D3-NI, high risk) |
| Malicious process started post-login | `propose_action(type="kill_process", params={"agent_id": <id>, "process_id": <pid>})` after evidence capture |

Order: block the source first; disable accounts only with evidence of success; isolate only with evidence
of compromise. Protected hosts/users are refused by policy. Rate limiting, MFA and password resets are human
follow-ups — record them with `add_finding`.

## 4. Eradication and recovery

- Reset credentials for any account that authenticated from the attacking source (human task).
- Remove attacker SSH keys, cron jobs and new accounts; confirm with FIM alerts and `get_agent_processes`.
- Harden: key-only SSH, lockout policy, MFA on remote access, no internet-facing RDP.
- Monitor the source and targeted accounts for 24–72 h; close when quiet.

## 5. Verification

The responder verifies executed actions (`wazuh_check_blocked_ip` with ip_address/agent_id,
`wazuh_check_user_status` with agent_id/username) and recommends rollback if a legitimate service is hit.

## 6. Evidence and records

- `add_finding` per stage with `standard_refs`, e.g. `NIST-800-61r3:Respond`, `MITRE-ATTACK:T1110.003`,
  `SANS-PICERL:Containment`, `PCI-DSS-4:Req 10`.
- Record source IPs + reputation, targeted accounts, attempt counts and window, first/last seen, success
  yes/no, and actions proposed/approved/verified.
- Detection gap (e.g. spraying below threshold)? Hand off to detection-engineer with the custom rule sketch above.
- Critical cases: hand off to reporting for the incident report.

## Escalation

| Condition | Escalate to |
|---|---|
| Successful login on a privileged/production account (rule 40112) | SOC lead + IR lead (human), severity critical |
| Distributed attack from > 50 sources | Network team (edge rate limiting) |
| Internal source | `ir-playbook-lateral-movement` |
