---
name: identity-compromise
description: Investigate suspected account compromise — brute force followed by success, impossible travel, privilege escalation and lateral movement across Linux and Windows; use when a user account appears in suspicious authentication activity.
allowed-tools: get_case get_wazuh_alerts search_security_events get_alerts_aggregated analyze_alert_patterns get_wazuh_agents add_entities add_finding link_mitre update_case
metadata:
  category: investigation
  display_name: Identity Compromise Investigation
  standards: [nist-800-61r3, mitre-attack, nist-800-53r5, cis-v8-1]
  version: "1.1"
---
# Identity Compromise Investigation

Accounts are the most common path to impact. Decide whether an account is compromised,
how far it was used, and what containment is justified.

## Key events and the Wazuh rules that surface them

Rule numbers are from the stock Wazuh 4.14 ruleset. Many Windows events are only
alerted on when the channel is collected and not filtered. If there's no rule, search
the raw event with `search_security_events` (field `data.win.system.eventID`). Load
`wazuh-windows-sysmon` for Windows field paths.

| Platform | Event | Wazuh rules | Meaning |
|---|---|---|---|
| Windows | Event ID 4624 | rule 60106 (level 3) | successful logon; check `data.win.eventdata.logonType`: 2 interactive, 3 network, 10 RemoteInteractive/RDP |
| Windows | Event ID 4625 | rules 60105, 60122 (level 5); burst → rule 60204 (level 10) | failed logon; `subStatus` separates bad password from unknown user |
| Windows | Event ID 4648 | none (search raw events) | logon with explicit credentials (runas, lateral tools) |
| Windows | Event ID 4672 | rule 67028 (level 3) | special privileges assigned: admin-equivalent logon. Low level, high meaning for non-admins |
| Windows | Event ID 4720, Event ID 4722 | rule 60109 (level 8) | account created / enabled |
| Windows | Event ID 4738 | rule 60110 (level 8) | account changed |
| Windows | Event ID 4728, Event ID 4732, Event ID 4756 | rules 60141, 60144, 60151 (level 5); rule 60154 Administrators group changed (level 12) | member added to security-enabled global / local / universal group |
| Windows | Event ID 4740 lockout | rule 60115 (level 9) | account locked out after multiple failures |
| Windows | Event ID 4768, Event ID 4771 | none stock (search raw events) | Kerberos TGT request / pre-auth failure: spraying against a DC |
| Linux | sshd failure | rules 5716, 5760 (level 5); rule 5710 non-existent user (level 5) | single failures |
| Linux | sshd burst | rules 5712, 5720, 5763 (level 10); rule 5758 max attempts exceeded (level 8) | composite brute-force rules |
| Linux | sshd success | rule 5715 (level 3) | `Accepted password` / `publickey` |
| Linux | sudo | rule 5402 to root (level 3), rule 5401 failed (level 5), rule 5403 first time for user (level 4) | privilege use |
| Linux | PAM | rule 5503 login failed (level 5), rule 5551 multiple failures (level 10) | console / other PAM services |
| Linux | account changes | rule 5902 new user (level 8), rule 5904 user information changed (level 8) | useradd / usermod |

## Procedure

1. List all auth events for the user over 7 days (`search_security_events(query="<user>")`),
   and aggregate by source IP and host (`get_alerts_aggregated`).
2. Establish baseline: usual source IPs, hosts, hours, logon types.
3. Test each hypothesis below; record which are supported.
4. Determine scope: every host the account touched after the suspected compromise time.

## Hypotheses and indicators

| Pattern | Indicators | ATT&CK |
|---|---|---|
| Brute force → success | rule 60204 or rules 5712, 5763 then rule 60106 or rule 5715 from the same source | T1110 → T1078 |
| Password spraying | one source, many users, few attempts each | T1110.003 |
| Impossible travel | successful logons from locations whose distance/time implies > ~900 km/h | T1078 |
| New source / off-hours | success from never-seen IP/ASN or outside baseline hours | T1078 |
| Privilege escalation | rule 67028 for a non-admin, group adds (rules 60141, 60144, 60154), rule 5402 by an unusual user | T1078.002/.003, T1098 |
| Lateral movement | same account, new hosts in short time; logon type 3/10 chains; SSH hops | T1021 (.001 RDP, .002 SMB, .004 SSH) |
| Persistence via account | new account created by the suspect account (rules 60109, 5902), SSH key added (FIM on `authorized_keys`, see `wazuh-fim-investigation`) | T1136, T1098.004 |

## Verdict

- **Compromised** — success from attacker-controlled source, or malicious actions by the
  account. Confidence ≥ 0.8.
- **Targeted, not compromised** — failures only, no success. Recommend blocking the source,
  not disabling the user.
- **Inconclusive** — anomalies without malicious actions; recommend user verification.

Recommend `disable_user` (proposed by `response-planner`) only with evidence of successful
malicious use. Service accounts
and break-glass accounts: flag the business impact explicitly; prefer blocking the
source or isolating the host first.

## Output

- `add_entities` (user as victim; source IPs as attacker; hosts touched).
- `link_mitre` for supported techniques.
- `update_case` severity/confidence.
- `add_finding` titled `Identity assessment: <user>` with baseline, hypotheses table
  (supported / not supported + evidence), hosts in scope, verdict, recommended
  containment. standard_refs: `NIST-800-61r3`, `CIS-v8.1:5` (Account Management),
  `CIS-v8.1:6` (Access Control Management).
