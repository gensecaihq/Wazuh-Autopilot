---
name: executive-reporting
description: Write shift, daily, weekly, executive and incident reports in BLUF style with risk expressed in business terms, and save them with save_report; use whenever a report or summary for humans is requested or scheduled.
allowed-tools: search_cases get_case list_actions get_wazuh_alert_summary get_wazuh_weekly_stats get_top_security_threats generate_security_report get_wazuh_vulnerability_summary save_report
metadata:
  category: reporting
  display_name: Executive Reporting
  standards: [nist-800-61r3, nist-csf-2]
  version: "1.0"
---
# Executive Reporting

Reports exist so humans can decide. Lead with the conclusion (BLUF — bottom line up
front), quantify, and translate technical risk into business impact.

## Style rules

- First paragraph: 2–3 sentences — the most important thing, its impact, and any
  decision needed.
- Numbers with comparison ("17 incidents, up 26% vs last week").
- Business language for executive reports: affected service, customers, revenue or
  regulatory exposure, downtime — not rule ids.
- Separate facts from assessments; use calibrated words (likely, very likely).
- No blame; name roles, not people.
- Keep executive reports ≤ 1 page; analyst reports can include tables.

## Data

| Need | Source |
|---|---|
| Cases in period | `search_cases(query="", status=...)` then `get_case` for top items |
| Actions | `list_actions(case_id)` for major cases |
| Alert volume | `get_wazuh_alert_summary`, `get_wazuh_weekly_stats` |
| Top threats | `get_top_security_threats` |
| Vulnerabilities | `get_wazuh_vulnerability_summary` |
| Pre-built summary | `generate_security_report` (use as input, verify numbers) |

## Templates

**Shift handover** (kind `shift`): open cases by severity · new since last shift ·
pending approvals (with expiry) · actions executed and verification status · watch items
for next shift.

**Daily** (`daily`): BLUF · alert volume and trend · incidents opened/closed · notable
cases (≤ 5, one line each) · automation stats · issues (agent coverage, ingestion lag).

**Weekly** (`weekly`): BLUF · KPIs vs prior week (see `soc-metrics`) · top ATT&CK
techniques · top targeted assets · vulnerability posture (Act/Attend counts) ·
detection tuning done/proposed · recommendations.

**Executive** (`executive`): BLUF · risk posture (improving / stable / worsening, why) ·
material incidents and business impact · decisions/investment asks · 3 KPIs max.

**Incident** (`incident`, per case — NIST 800-61r3 post-incident style): summary ·
timeline (from `incident-timeline`) · impact · root cause / initial access · actions and
verification · what went well · what to improve (detection, process, controls) ·
follow-up items with owner roles.

## Output

- `save_report(kind, title, body_md)` where kind ∈ `shift|daily|weekly|monthly|executive|incident`.
- Title format: `<Kind> report — <period or case number>`.
- Include a "Data sources" footer listing tools used and the time range.
