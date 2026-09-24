---
name: wazuh-windows-sysmon
description: Interpret Wazuh Windows EventChannel and Sysmon alerts — logon, privilege, account and service events, Sysmon detection groups, field paths and logon types — mapping Windows Event IDs to Wazuh rules; use for any Windows or Sysmon alert and for Windows-focused hunts.
allowed-tools: get_wazuh_alerts search_security_events get_alerts_aggregated get_wazuh_rules_summary get_case search_cases add_finding link_mitre
metadata:
  category: detection
  display_name: Wazuh Windows and Sysmon
  standards: [mitre-attack, nist-csf-2, cis-v8-1, sigma]
  version: "1.0"
---
# Wazuh Windows and Sysmon

Windows logs reach Wazuh through the EventChannel collector and are decoded as JSON under `data.win.*`.
Security-log rules live in the `windows_security` group; Sysmon rules in the `sysmon` group.

## Field paths

| Field | Content |
|---|---|
| `data.win.system.eventID` | Windows Event ID |
| `data.win.system.channel` | `Security`, `System`, `Microsoft-Windows-Sysmon/Operational`, … |
| `data.win.system.computer` | Host name as Windows reports it |
| `data.win.eventdata.targetUserName` / `subjectUserName` | Account acted on / acting account |
| `data.win.eventdata.logonType` | Logon type (below) |
| `data.win.eventdata.ipAddress` / `workstationName` | Source of a network logon |
| `data.win.eventdata.status` / `subStatus` | Failure reason codes |
| `data.win.eventdata.image`, `parentImage`, `commandLine`, `hashes` | Sysmon process fields |
| `data.win.eventdata.destinationIp`, `destinationPort` | Sysmon network fields |
| `data.win.eventdata.targetObject` | Sysmon registry target |

## Security log: Event ID → Wazuh rule

| Windows event | Wazuh rule (level) | Notes |
|---|---|---|
| Event ID 4624 logon success | rule 60106 (level 3) | Workstation variant: rule 60118 (level 3) |
| Event ID 4625 logon failure | rule 60122 (level 5) | Parent: rule 60105 (level 5) |
| Repeated Event ID 4625 | rule 60204 (level 10) | Correlation: multiple Windows logon failures within 240s |
| Event ID 4740 account locked out | rule 60115 (level 9) | |
| Event ID 4720 / Event ID 4722 account created / enabled | rule 60109 (level 8) | |
| Event ID 4738 account changed | rule 60110 (level 8) | |
| Administrators group changed | rule 60154 (level 12) | Privilege escalation / persistence |
| Event ID 4672 special privileges assigned | rule 67028 (level 3) | In the WEF baseline ruleset; noisy on its own — join with 4624 for the same logon |
| Event ID 1102 audit log cleared | rule 60117 (level 9) | Also rule 593 (level 9, "Microsoft Event log cleared") — defence evasion, always investigate |
| Audit policy changed | rule 60112 (level 8) | |
| Event ID 7045 new service installed (System log) | rule 61138 (level 5) | Persistence / lateral movement (PsExec creates a service) |

## Logon types

2 interactive, 3 network (SMB, most lateral movement), 4 batch, 5 service, 7 unlock, 8 network
cleartext, 9 new credentials (runas /netonly; pass-the-hash indicator with NTLM), 10 remote interactive
(RDP), 11 cached. Type 3 or 10 from workstation to workstation is unusual in most environments.

## Sysmon detection groups

Sysmon events are decoded under generic `sysmon_event*` groups; Wazuh's behavioural detections sit in
`sysmon_eid*_detections` groups — query these, not the raw event groups:

| Group | Sysmon event | Example rules |
|---|---|---|
| `sysmon_eid1_detections` | Process creation | rule 92000 (level 4, scripting interpreter spawned a new process), rule 92002 (level 6, scripting interpreter spawned a Windows command shell) |
| `sysmon_eid3_detections` | Network connection | rule 92104 (level 15, suspicious binary created network connection), rule 92103 (level 6, LDAP activity from PowerShell) |
| `sysmon_eid7_detections` | Image loaded | rule 92151 (level 12, binary loaded PowerShell automation library — unmanaged PowerShell) |
| `sysmon_eid8_detections` | CreateRemoteThread | rule 92400 (level 12, possible code injection on explorer.exe) |
| `sysmon_eid10_detections` | Process access | rule 92900 (level 12, LSASS accessed with read permissions — credential dumping) |
| `sysmon_eid11_detections` | File created | rule 92213 (level 15, executable dropped in folder commonly used by malware) |
| `sysmon_eid13_detections` | Registry value set | rule 92301 (level 12, suspicious file extension in registry ASEP), rule 92307 (level 3, new service creation found in registry) |

Sysmon Event ID 22 (DNS query) is decoded (group `sysmon_event_22`) but the stock ruleset has few
detections on it — DNS hunting needs custom rules (example to create: custom rule 100400 for queries to
newly registered domains).

## Procedure

1. Read `data.win.system.eventID`, channel and the key eventdata fields before the rule description.
2. For authentication: build the sequence per account and source — failures (rule 60122) → lockout
   (rule 60115) or success (rule 60106) → privileges (rule 67028) → group change (rule 60154).
   Success after a failure burst from the same source is the escalation point.
3. For process detections: parent → child → command line → network → file drops, all on the same
   agent within minutes (`get_wazuh_alerts agent_id="<id>" rule_groups=["sysmon"]`).
4. Check prevalence with `get_alerts_aggregated` before calling a rule "suspicious" — some Sysmon rules
   fire constantly for admin tooling.
5. Map to ATT&CK from the behaviour (see mitre-attack-mapping); `rule.mitre` is a hint.

## Noise

Service accounts with type 5 logons, backup/monitoring accounts, SCCM/Intune, Windows Update spawning
scripting hosts, IT admin PowerShell. Record the benign pattern so detection-engineer can scope a
level-0 child rule.

## Output

`add_finding` with the Event ID sequence (account, source IP/workstation, logon type, timestamps),
Sysmon process chain and verdict; `link_mitre` for supported techniques (e.g. T1110, T1078, T1021.001,
T1543.003, T1070.001, T1003.001, T1055).
