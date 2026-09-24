---
name: compliance-mapping
description: Map incidents, control checks and SCA results to ISO 27001:2022, PCI DSS v4.0.1, NIST SP 800-53r5 and CIS Controls v8.1 and write auditor-ready evidence statements; use for compliance checks, audit questions, or incidents on regulated assets.
allowed-tools: run_compliance_check get_sca_policy_checks get_iso27001_dashboard get_iso27001_gap_analysis get_iso27001_control_detail get_iso27001_alerts get_wazuh_agents get_wazuh_alerts get_case add_finding save_report
metadata:
  category: compliance
  display_name: Compliance Mapping
  standards: [iso-27001-2022, pci-dss-4, nist-800-53r5, cis-v8-1, nist-csf-2]
  version: "1.1"
---
# Compliance Mapping

Translate security evidence into control language auditors accept. You report status
and gaps; you don't certify compliance.

## Tools

| Need | Tool |
|---|---|
| Framework check | `run_compliance_check(framework="PCI-DSS", agent_id=...)`; `framework` is one of PCI-DSS, HIPAA, SOX, GDPR, NIST, ISO27001; omit `agent_id` for the whole environment |
| CIS benchmark / SCA results per agent | `get_sca_policy_checks(agent_id)` |
| ISO 27001 posture | `get_iso27001_dashboard` |
| ISO 27001 gaps | `get_iso27001_gap_analysis` |
| One ISO control | `get_iso27001_control_detail(control_id="A.8.16")` |
| Alerts tagged to ISO controls | `get_iso27001_alerts` |

### Wazuh compliance tags

Stock Wazuh rules declare compliance mappings as groups in the ruleset (`pci_dss_10.2.4`,
`gdpr_IV_32.2`, `hipaa_164.312.b`, `nist_800_53_AC.7`, `tsc_CC6.1`, `gpg13_7.1`). In alerts
Wazuh emits them as arrays: `rule.pci_dss`, `rule.gdpr`, `rule.hipaa`, `rule.nist_800_53`,
`rule.tsc`, `rule.gpg13`. For example, rule 5712 (sshd brute force) carries PCI DSS
10.2.4 / 10.2.5 / 11.4, NIST 800-53 AC.7 / AU.14 / SI.4, HIPAA 164.312.b and TSC
CC6.1 / CC6.8 / CC7.2 / CC7.3.

- Use them as evidence hints: `get_wazuh_alerts` on the scope and period, then count
  alerts per tag to show that monitoring for a requirement is producing events.
- They map *detections* to requirements. They don't prove a control is effective.
  Pair them with SCA results (`get_sca_policy_checks`) for configuration requirements.
- There is no ISO 27001 tag in the stock ruleset. The MCP ISO tools
  (`get_iso27001_*`) do that mapping server-side.
- The PCI tags refer to the requirement numbering the rule was written against. Check
  it against v4.0.1 wording before citing it in an audit statement.

Load `wazuh-sca-hardening` for CIS benchmark and SCA detail (rule 19011 is a check that
went from passed to failed, level 9).

## Framework anchors (category level — cite specific controls only when confident)

| Topic | ISO 27001:2022 Annex A | PCI DSS v4.0.1 | NIST 800-53r5 | CIS v8.1 |
|---|---|---|---|---|
| Logging & monitoring | A.8.15 Logging, A.8.16 Monitoring activities | Req 10 | AU family, SI-4 | Control 8 |
| Incident management | A.5.24–A.5.28 | Req 12.10 | IR family | Control 17 |
| Vulnerability mgmt | A.8.8 Management of technical vulnerabilities | Req 6, Req 11 | RA-5, SI-2 | Control 7 |
| Access control / accounts | A.5.15–A.5.18, A.8.2, A.8.5 | Req 7, Req 8 | AC, IA families | Controls 5, 6 |
| Configuration / hardening | A.8.9 Configuration management | Req 2 | CM family | Control 4 |
| Malware protection | A.8.7 | Req 5 | SI-3 | Control 10 |
| File integrity | A.8.9 / A.8.16 (supporting) | Req 11.5 (change detection) | SI-7 | Control 3 (data protection, supporting) |
| Network security | A.8.20–A.8.22 | Req 1 | SC family | Controls 12, 13 |

## Procedure

1. Define scope: framework, assets (agent ids / groups), period.
2. Run the relevant checks; collect pass/fail counts and failing items.
3. For incidents: identify which controls failed or worked (e.g. detection worked →
   monitoring control effective; unpatched CVE exploited → vulnerability management gap).
4. Write evidence statements and gaps.

## Evidence statement format

```
Control: ISO 27001:2022 A.8.16 Monitoring activities
Status: Effective | Partially effective | Not effective | Not assessed
Evidence: Wazuh agents active on 142/145 in-scope hosts (get_wazuh_agents, 2026-03-24);
          INC-0042 detected within 4 minutes of initial access.
Gap: 3 hosts without active agents (list); no alerting on log-collector errors
     (ask platform-engineer for ingestion health evidence).
Recommendation: <action + owner role>
```

Be factual: cite tool, date, and numbers. "Not assessed" beats guessing.

## Output

- `save_report(kind="compliance", title, body_md)` for audits: scope, summary score per
  framework, control table, gaps with priority.
- On incidents, `add_finding` titled `Compliance impact` listing affected controls and
  any notification obligations a human must review (e.g. PCI incident response,
  breach-notification regimes). standard_refs: e.g. `ISO-27001:A.8.16`, `PCI-DSS-4:10`,
  `NIST-800-53r5:SI-4`, `CIS-v8.1:8`.
