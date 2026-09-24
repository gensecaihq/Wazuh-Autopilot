---
name: wazuh-fim-investigation
description: Investigate Wazuh File Integrity Monitoring (syscheck) alerts — file and registry add/modify/delete events, checksums, permissions and who-data — separate tampering from routine change and pivot to processes and users; use for any syscheck alert or suspected persistence/tampering.
allowed-tools: get_wazuh_alerts search_security_events get_alerts_aggregated get_wazuh_agents get_wazuh_rules_summary get_case search_cases update_case add_entities add_finding link_mitre
metadata:
  category: investigation
  display_name: Wazuh FIM Investigation
  standards: [nist-csf-2, mitre-attack, pci-dss-4, cis-v8-1, iso-27001-2022]
  version: "1.0"
---
# Wazuh FIM Investigation

Wazuh FIM (syscheck) alerts on changes to monitored files and Windows registry entries. The question is
always: **expected change (patching, config management) or tampering/persistence?**

## Core syscheck rules (stock ruleset)

| Event | Files | Windows registry key | Windows registry value |
|---|---|---|---|
| Modified | rule 550 (level 7) | rule 594 (level 5) | rule 750 (level 5) |
| Deleted | rule 553 (level 7) | rule 597 (level 5) | rule 751 (level 5) |
| Added | rule 554 (level 5) | rule 598 (level 5) | rule 752 (level 5) |

Groups: `syscheck`, plus `syscheck_entry_modified` / `syscheck_entry_deleted` / `syscheck_entry_added`
and `syscheck_file` / `syscheck_registry`. Query by group:
`get_wazuh_alerts rule_groups=["syscheck"] agent_id="<id>" timestamp_start="now-24h"`.

FIM health signals (monitoring gaps, not attacks): rule 560 (level 7, "FIM real-time queue is full")
and rule 233 (level 12, "The maximum limit of files monitored has been reached") mean changes may have
been missed — record it and hand off to platform-engineer.

## Key fields

| Field | Use |
|---|---|
| `syscheck.path` | What changed |
| `syscheck.event` | added / modified / deleted |
| `syscheck.mode` | `realtime`, `whodata` or `scheduled` — scheduled scans only tell you the change happened since the last scan |
| `syscheck.md5_before/after`, `sha1_*`, `sha256_*` | Content change; hashes go to threat-intel for reputation |
| `syscheck.size_before/after` | Truncation, appended payloads |
| `syscheck.perm_before/after`, `uname_*`, `gname_*`, `uid_*` | Permission / ownership changes (e.g. SUID, world-writable) |
| `syscheck.changed_attributes` | Which attributes changed |
| `syscheck.diff` | Text diff (only when `report_changes` is enabled for the path) |
| `syscheck.audit.user.name`, `.audit.effective_user.name`, `.audit.process.name`, `.audit.process.id`, `.audit.process.ppid` | **Who-data**: which user and process made the change (Linux auditd / Windows SACL) |

If `syscheck.audit.*` is absent the path isn't in who-data mode — you know **what** changed, not **who**.
Say so rather than guessing.

## High-value paths

| Linux | Why |
|---|---|
| `/etc/passwd`, `/etc/shadow`, `/etc/group`, `/etc/sudoers`, `/etc/sudoers.d/*` | Account creation, privilege (T1136, T1548) |
| `/root/.ssh/authorized_keys`, `~/.ssh/authorized_keys` | Persistence via keys (T1098.004) |
| `/etc/crontab`, `/etc/cron.*`, `/var/spool/cron/*` | Scheduled persistence (T1053.003) |
| `/etc/systemd/system/*`, `/lib/systemd/system/*`, `/etc/init.d/*` | Service persistence (T1543.002) |
| `/etc/ld.so.preload`, `/etc/profile.d/*`, `~/.bashrc` | Hijacking / shell persistence |
| Web roots (`/var/www/*`) | Web shells (T1505.003) |
| Binaries in `/bin`, `/usr/bin`, `/usr/sbin` | Trojaned tools |

| Windows | Why |
|---|---|
| `HKLM\...\CurrentVersion\Run`, `RunOnce`, `HKCU` equivalents | Logon persistence (T1547.001) |
| `HKLM\SYSTEM\CurrentControlSet\Services\*` | Service creation/modification (T1543.003) |
| Startup folders | Persistence |
| `C:\Windows\System32\drivers\etc\hosts` | Traffic redirection |
| `C:\Windows\System32\*` executables | Binary replacement |

## Procedure

1. **Scope**: pull all syscheck alerts for the agent in the window; list changed paths.
2. **Baseline the change**: check for package activity in the same window — rule 2902 (level 7, "New dpkg
   (Debian Package) installed"), rule 2903 (dpkg removed), rule 2932 (level 7, "New Yum package installed"),
   rule 2933 (Yum package updated). A binary modified minutes after a matching package update is
   probably routine; the same change with no package activity is suspicious.
3. **Correlate with account events**: rule 5902 (level 8, "New user added to the system"),
   rule 5901 (level 8, "New group added to the system"), rule 5904 (level 8, "Information from the user
   was changed"), rule 2833 (level 8, "Root's crontab entry changed").
4. **Who did it**: use who-data if present; otherwise look for logins/sudo on the agent around the change
   (e.g. rule 5402 (level 3, "Successful sudo to ROOT executed")).
5. **Process context**: if a process is implicated, hand off to investigation (it holds
   `get_agent_processes` / `get_agent_ports`) unless you are investigation.
6. **Hashes**: send `sha256_after` of new/modified executables to threat-intel for reputation.
7. **Deletions**: bulk rule 553 on data directories plus new files with unusual extensions is a
   ransomware pattern — escalate immediately (see ir-playbook-ransomware).

## Noise

Log rotation, package managers, configuration management (Ansible/Puppet/Chef runs at fixed times),
antivirus definition updates, and editors creating temp files. Suggest a scoped level-0 child rule via
detection-engineer rather than disabling FIM on a path.

## Output

- `add_entities`: file paths (type `file`), hashes (type `hash`), user and process from who-data.
- `link_mitre` for the persistence/tampering technique you can support with evidence.
- `add_finding`: what changed, when, who (or "who-data not enabled"), routine-vs-suspicious verdict with
  the evidence (package event present/absent), and standard refs such as `MITRE-ATTACK:T1547.001`,
  `PCI-DSS-4:11.5`, `CIS-v8.1:3`.
