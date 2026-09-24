---
name: wazuh-sca-hardening
description: Use Wazuh Security Configuration Assessment (SCA) results — CIS policy scores, failed checks and regressions — to prioritize hardening and map it to CIS Controls, PCI DSS and ISO 27001; use for hardening reviews, compliance evidence, or when a vulnerability or incident points to a misconfiguration.
allowed-tools: get_sca_policy_checks get_wazuh_agents get_wazuh_alerts get_case search_cases add_finding save_report
metadata:
  category: compliance
  display_name: Wazuh SCA Hardening
  standards: [cis-v8-1, pci-dss-4, iso-27001-2022, nist-800-53r5, nist-csf-2]
  version: "1.0"
---
# Wazuh SCA Hardening

Wazuh SCA runs policy files (mostly CIS Benchmarks: `cis_ubuntu22-04`, `cis_win2022`, `cis_rhel9`, …) on
each agent and reports each check as **passed**, **failed** or **not applicable**, plus an overall score.

## SCA rules (stock ruleset, group `sca`)

| Rule | Level | Meaning |
|---|---|---|
| rule 19001 | 3 | SCA summary: policy score |
| rule 19002 | 4 | Score less than 90% |
| rule 19003 | 5 | Score less than 80% |
| rule 19004 | 7 | Score less than 50% |
| rule 19005 | 9 | Score less than 30% |
| rule 19007 | 7 | Check result **failed** (`sca.check.result: failed`) |
| rule 19008 | 3 | Check result passed |
| rule 19009 | 3 | Check result not applicable |
| rule 19010 | 3 | Status changed from failed to passed (remediated) |
| rule 19011 | 9 | Status changed from **passed to failed** (regression) |
| rule 19012 | 5 | Status changed from passed to not applicable |

A **regression** (rule 19011) is the most important SCA signal: something that was compliant stopped
being compliant. It can mean drift, a bad change — or an attacker weakening a host (disabling auditing,
enabling root SSH login). Treat regressions on servers as potential incidents, not just hygiene.

## Key fields

`sca.policy`, `sca.policy_id`, `sca.check.id`, `sca.check.title`, `sca.check.result`,
`sca.check.previous_result`, `sca.check.rationale`, `sca.check.remediation`, `sca.check.compliance.*`
(CIS, PCI DSS, NIST 800-53, HIPAA, ISO mappings shipped in the policy), `sca.score`, `sca.passed`,
`sca.failed`.

## Getting the data

- Current state: `get_sca_policy_checks agent_id="<id>"` (optionally `policy_id`) — returns checks with
  result, rationale and remediation.
- Changes over time: `get_wazuh_alerts rule_groups=["sca"] agent_id="<id>" timestamp_start="now-7d"`;
  regressions only: filter the `rule_id` parameter on rule 19011.
- Fleet view: iterate agents from `get_wazuh_agents status="active"` — keep it to the in-scope set
  (servers, internet-facing, crown jewels) to stay within budget.

## Prioritizing failed checks

Score each failed check, highest first:

1. **Exposure**: internet-facing or crown-jewel host > internal server > workstation.
2. **Attack relevance**: checks that directly enable known techniques — remote root login, password
   authentication on SSH, SMBv1, missing audit logging, world-writable system paths, no host firewall,
   unpatched auto-update disabled.
3. **CIS profile**: Level 1 checks are baseline and cheap; Level 2 checks are defence-in-depth.
4. **Correlation**: a failed check on a host that also has related alerts or critical vulnerabilities
   moves to the top (hand off vulnerability context to vuln-management if you are compliance).
5. **Effort**: note likely breakage (e.g. disabling a service in use).

## Mapping to frameworks

| Area | CIS Controls v8.1 | PCI DSS v4.0.1 | ISO/IEC 27001:2022 |
|---|---|---|---|
| Secure configuration | CIS 4 | Req 2 | A.8.9 |
| Audit logging | CIS 8 | Req 10 | A.8.15 |
| Vulnerability / patch | CIS 7 | Req 6 | A.8.8 |
| Access control / accounts | CIS 5, CIS 6 | Req 7, Req 8 | A.5.15, A.8.2 |
| Network defence / firewall | CIS 12, CIS 13 | Req 1 | A.8.20 |

Prefer the mapping shipped in `sca.check.compliance.*` when present; the table is a fallback.

## Remediation hand-off

SCA findings are fixed by system owners, not by Wazuh active response. Record remediation as a
recommendation: check ID, title, affected agents, remediation text from the policy, and the priority.
Regressions that look deliberate on a sensitive host go to triage as a new case.

## Output

- `add_finding` per host or per theme: score, failed check count, top failed checks with remediation,
  regressions with timestamps, and refs such as `CIS-v8.1:4`, `PCI-DSS-4:Req 2`, `ISO-27001:A.8.9`.
- `save_report` (kind `compliance`) for fleet reviews: score distribution, worst hosts, top recurring
  failures, regressions since last review.
