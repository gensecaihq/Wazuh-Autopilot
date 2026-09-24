---
name: host-forensics
description: Live triage of a Wazuh-monitored host — processes, listening ports, configuration, agent health, persistence locations — with evidence-handling notes; use when a specific endpoint is suspected of compromise.
allowed-tools: get_wazuh_agents check_agent_health get_agent_processes get_agent_ports get_agent_configuration get_wazuh_alerts search_security_events get_wazuh_vulnerabilities get_sca_policy_checks get_case add_entities add_finding link_mitre
metadata:
  category: investigation
  display_name: Host Forensics
  standards: [nist-800-61r3, nist-800-53r5, mitre-attack, sans-picerl]
  version: "1.1"
---
# Host Forensics

Remote, read-only live response through the Wazuh agent's inventory (syscollector) and
alert history. You cannot image disks or run commands; you work from what the agent
reports. Be explicit about that limitation in findings.

## Procedure

1. Identify the agent: `get_wazuh_agents` (match name/IP) → `agent_id`, OS, version,
   last keepalive.
2. `check_agent_health` — a disconnected or stale agent means inventory may be old;
   record the inventory timestamp. Syscollector inventories run on an interval (1 hour by
   default), so a short-lived process may never appear, and a killed one may still be
   listed until the next scan. Compare `scan.time` with the incident time.
3. `get_agent_processes(agent_id)` — review with the heuristics below.
4. `get_agent_ports(agent_id)` — listening and established sockets.
5. `get_agent_configuration(agent_id)` — confirm FIM/rootcheck/log collection is
   enabled; attackers disable monitoring.
6. `get_wazuh_alerts(agent_id=..., timestamp_start="now-7d")` — FIM
   (rules 550, 553, 554; registry rules 594, 598, 750, 752), rootcheck
   (rule 510; rule 513 Windows malware), SCA (rule 19011 check passed → failed) and audit
   events for persistence evidence. Load `wazuh-fim-investigation` and `wazuh-malware-detection` for detail.
7. `get_wazuh_vulnerabilities(agent_id)` and `get_sca_policy_checks(agent_id)` — the likely
   way in (unpatched service, weak configuration) matters for eradication.

## Suspicious process heuristics

| Signal | Why |
|---|---|
| Interpreter children of web/database servers (`w3wp`, `httpd`, `nginx`, `java`, `sqlservr` → `cmd`, `powershell`, `sh`, `bash`) | web shell / exploitation (T1505.003, T1059) |
| Binaries running from `/tmp`, `/dev/shm`, `/var/tmp`, `%TEMP%`, `%APPDATA%`, `C:\Users\Public` | staging / malware |
| Names mimicking system binaries in wrong paths (`svchost.exe` outside System32, `[kworker]` with a real exe path) | masquerading (T1036) |
| Encoded / obfuscated command lines (`-enc`, `FromBase64String`, `curl | sh`) | T1059, T1027 |
| Known tools: `mimikatz`, `procdump` targeting lsass, `nc -e`, `socat`, `chisel`, `rclone` | credential access / tunneling / exfil |
| Processes owned by root/SYSTEM that are normally user-level | privilege escalation |

Syscollector process fields to use: `name`, `cmd` + `argvs`, `ppid` (look up the
parent), `euser` / `ruser`, `start_time`. Port fields: `local.ip`, `local.port`,
`remote.ip`, `remote.port`, `state`, `process`, `pid`.

## Suspicious port heuristics

- Listeners on high ports bound to 0.0.0.0 not in the host's known baseline.
- Established connections to external IPs on uncommon ports, or from server processes
  that shouldn't initiate outbound traffic.
- Common backdoor/tunnel ports (4444, 1337, 31337, 8081 on non-web hosts) — hint only.

## Persistence locations to check (via FIM/audit alerts)

Linux: `/etc/crontab`, `/etc/cron.*`, `/var/spool/cron`, `/etc/systemd/system`,
`~/.ssh/authorized_keys`, `/etc/rc.local`, `/etc/ld.so.preload`, shell profiles
(`~/.bashrc`, `/etc/profile.d`), new users in `/etc/passwd`, sudoers changes.

Windows: Run/RunOnce registry keys (FIM registry alerts, rules 750, 752), services
(Event ID 7045, Event ID 4697), scheduled tasks (Event ID 4698), Startup folders, WMI event
subscriptions (Sysmon Event ID 19–21), new local admins (Event ID 4732 → rule 60144;
Administrators group change → rule 60154).

FIM only reports paths it monitors (`get_agent_configuration` → `syscheck`). An
unmonitored persistence path produces no alert, so record it as a monitoring gap
rather than "clean".

## Evidence handling

Follow NIST 800-86-style practice even for remote data:
- Record for each artefact: source tool, agent id, timestamp of collection, and the
  inventory timestamp the agent reported.
- Quote exact values (paths, PIDs, hashes); don't paraphrase.
- Note anything that could be lost (volatile process/socket state) so humans can
  prioritize a proper acquisition before containment actions like reboot.
- Recommend isolation over kill/restart when forensic acquisition is still needed.

## Output

- `add_entities` for suspicious processes, files, hashes, remote IPs (validated).
- `link_mitre` for confirmed techniques.
- `add_finding` titled `Host forensics: <host>` with: agent status, suspicious
  processes/ports table, persistence evidence, monitoring gaps, evidence log, verdict
  (clean / suspicious / compromised) and confidence. standard_refs: `NIST-800-61r3`.
