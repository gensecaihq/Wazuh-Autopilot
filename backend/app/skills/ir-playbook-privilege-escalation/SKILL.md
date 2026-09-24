---
name: ir-playbook-privilege-escalation
description: Incident-response playbook for privilege escalation on Linux and Windows — sudo/su abuse, SUID and capability misuse, kernel modules and exploits, sudoers/cron/systemd tampering, UAC bypass, admin-group changes and process injection; use when Wazuh raises escalation indicators (e.g. rules 5404, 5405, 5302, 80721, 92046, 92055, 60154) or a user gains unexpected root/SYSTEM.
allowed-tools: get_wazuh_alerts search_security_events get_wazuh_agents get_agent_processes get_agent_ports check_agent_health get_case search_cases update_case add_entities link_mitre add_finding list_actions wazuh_check_user_status wazuh_check_process wazuh_check_agent_isolation wazuh_check_file_quarantine
metadata:
  category: response
  display_name: IR Playbook — Privilege Escalation
  standards: [nist-800-61r3, sans-picerl, mitre-attack, mitre-d3fend, nist-800-53r5, cis-v8-1, iso-27001-2022]
  version: "2.1"
---
# IR Playbook — Privilege Escalation

Severity **critical** when escalation succeeds. MITRE ATT&CK TA0004: T1548 (.001 SUID, .002 UAC bypass,
.003 sudo), T1068 (exploitation), T1055 (process injection), T1053.003 (cron), T1543 (services),
T1547.006 (kernel modules), T1098 / T1484 (account and group changes). Rule IDs are from the stock Wazuh 4.14
ruleset (levels official). Full procedure and forensic commands: `references/playbook.md`.

## 1. Detection signals

| Signal | Wazuh rules (level) | Notes |
|---|---|---|
| sudo failures | rules 5401 (L5), 5404 (L10, three failures), 5405 (L5, user not in sudoers) | group `sudo` |
| sudo to root / first-time sudo | rules 5402 (L3), 5403 (L4) | low level on their own — escalate when the user or command is unusual |
| su to root | rules 5302 (L9, failed su to root), 5303 (L3, successful su to root) | group `su` |
| auditd root transition | rules 80721 (L10, user becomes root), 80742 (L5, user ID changed) | requires auditd |
| New user / group, account changes (Linux) | rules 5902 (L8), 5901 (L8), 5904 (L8), 2961 (L5, user added to group sudo) | group `adduser` |
| Root crontab changed | rule 2833 (L8) | persistence after escalation |
| Unsigned / untrusted kernel module loaded | rules 5132 (L11), 5133 (L11) | T1547.006; kernel exploit/rootkit indicator |
| Critical file changes (FIM) | rules 550 (L7), 554 (L5) on `/etc/sudoers*`, `/etc/passwd`, `/etc/shadow`, systemd units | group `syscheck`; paths must be monitored |
| Windows UAC bypass | rules 92046 (L12, fodhelper), 92055 (L12), 92056 (L14), 92305 (L12), 92306 (L12) | Sysmon Event IDs 1 / 13 |
| Windows admin group changes | rules 60154 (L12, Administrators group), 60179 (L10, Remote Desktop Users), 60144 (L5, local group member added) | Security log Event ID 4732 |
| Special privileges on logon | rule 67028 (L3, Event ID 4672) | only meaningful for non-admin accounts |
| Process injection | rules 92400 (L12), 92910 (L12) | Sysmon Event IDs 8 / 10 |

Stock gaps (org must create, range 100000–120000): SUID/`setcap` use with GTFOBins arguments (`custom rule 100610`,
auditd execve on `chmod`/`setcap`), `pkexec` abuse (`custom rule 100613`), systemd units created outside the package
manager (`custom rule 100616`, FIM on `/etc/systemd/system`). Validate with `wazuh-logtest` before enabling.

High-confidence patterns: web-server user (www-data, apache, IIS AppPool) spawning a root shell; new UID-0 account;
sudoers change followed by sudo use; exploit for a CVE present on the host.

## 2. Triage / investigation (investigation agent)

1. Context: `get_wazuh_alerts` for the host (`agent_id`, `timestamp_start: "now-24h"`,
   `rule_groups: ["sudo","su","adduser","syscheck"]`), `search_cases` for the host and user.
2. Answer:
   - Which user escalated, from what to what (user → root/SYSTEM)? Expected for that user?
   - Method (sudo, su, SUID, kernel, service/cron, UAC bypass, group change)? Did it **succeed**?
   - Parent process: interactive admin session vs web shell / service account?
   - Production or crown-jewel host? (`get_wazuh_agents`)
3. Host evidence: `get_agent_processes` (root processes whose ancestry leads to a non-privileged user or web
   server, shells spawned by services); `get_agent_ports` (new listeners opened as root); `check_agent_health`.
   The investigation agent can also check `get_wazuh_vulnerabilities` for a local-privesc CVE (kernel, sudo,
   polkit) that matches the observed exploit — hand confirmed CVEs to vuln-management.
4. Fleet sweep: `search_security_events` for the same user/technique on other hosts; novel technique → hand off
   to threat-hunter.
5. `add_entities` (user, host with `agent_id`, suspicious files, process), `link_mitre`, `update_case`
   (attempt only → high; successful escalation or UID-0 creation → critical), and `add_finding` with a
   containment **recommendation to response-planner**.

## 3. Response (response-planner)

Check state first (`wazuh_check_user_status`, `wazuh_check_process`), then propose:

| Situation | Proposal |
|---|---|
| Compromised local account used to escalate | `propose_action(type="disable_user", params={"agent_id": <host>, "username": <user>})` (D3-AL) |
| Root shell / exploit process running | `propose_action(type="kill_process", params={"agent_id": <host>, "process_id": <pid>})` (D3-PT) after evidence |
| Dropped exploit or malicious SUID binary | `propose_action(type="quarantine_file", params={"agent_id": <host>, "file_path": <path>})` (D3-FEV) |
| Confirmed root compromise | `propose_action(type="isolate_host", params={"agent_id": <host>})` (D3-NI; supervised) |
| External C2 from the host | `propose_action(type="block_ip", params={"ip_address": <c2>, "agent_id": <host>})` |

Order: capture process tree and hashes → isolate (if root compromise) → kill → quarantine → disable account.
Never target `root`/`Administrator` (protected); record credential resets for humans with `add_finding`.

## 4. Eradication and recovery

- Remove persistence: sudoers entries, UID-0 accounts, SUID bits, cron jobs, systemd units, keys.
- Patch the exploited vulnerability; reboot into the fixed kernel where relevant.
- Rebuild (don't clean) hosts with confirmed root/SYSTEM compromise; record the decision.
- Reset credentials of every account present on the host.

## 5. Verification

The responder checks `wazuh_check_user_status`, `wazuh_check_process`, `wazuh_check_file_quarantine`,
`wazuh_check_agent_isolation` for executed actions and records results.

## 6. Evidence and records

- Process ancestry, command lines, file hashes, sudoers/passwd diffs as findings
  (`MITRE-ATTACK:T1548.003`, `NIST-800-53r5:IR-4`, `ISO-27001:A.5.28`).
- Coverage gaps (e.g. no auditd for `setcap`) → hand off to detection-engineer.
- Hand off to reporting for the incident report with root cause (vulnerability vs misconfiguration vs stolen creds).

## Escalation

| Condition | Escalate to |
|---|---|
| Root/SYSTEM on production or a DC | IR lead (human); forensic imaging before rebuild |
| Kernel 0-day suspected | Vendor + vulnerability management; `ir-playbook-vulnerability-spike` |
| Web shell origin | Web application owner; check data access (`ir-playbook-data-exfiltration`) |
