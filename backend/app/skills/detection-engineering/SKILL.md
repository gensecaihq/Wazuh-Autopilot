---
name: detection-engineering
description: Design, backtest and tune detections as code — ADS-documented Sigma or Wazuh rules with ATT&CK coverage — and submit them via propose_detection for human review; use for detection gaps, recurring false positives or new TTPs from hunts and incidents.
allowed-tools: get_case get_wazuh_alerts search_security_events get_alerts_aggregated analyze_alert_patterns get_wazuh_rules_summary propose_detection add_finding save_report
metadata:
  category: detection
  display_name: Detection Engineering
  standards: [sigma, mitre-attack, nist-csf-2, cis-v8-1]
  version: "1.1"
---
# Detection Engineering

Detections are code: versioned, documented, tested, reviewed. You propose; humans
review and deploy. Never claim a rule is deployed.

## Inputs that trigger work

- Hunt found activity with no alert (detection gap).
- Incident where first detection was late (dwell time > 0).
- Rule producing repeated false positives (tuning).
- New TTP from threat intel relevant to the environment.

## ADS (Alerting and Detection Strategy) — Palantir framework

Every proposal documents:
1. **Goal** — what behaviour it detects.
2. **Categorization** — ATT&CK tactic/technique.
3. **Strategy Abstract** — how, at a high level.
4. **Technical Context** — data sources, fields, platform details.
5. **Blind Spots and Assumptions** — what it misses, what must be true.
6. **False Positives** — known benign triggers.
7. **Validation** — how to generate a true positive to test it.
8. **Priority** — alert severity and why.
9. **Response** — what the analyst should do when it fires.

## Rule formats

Prefer **Sigma** (portable) with a Wazuh mapping note; use native **Wazuh XML** when the
logic depends on Wazuh decoders or `if_sid` chaining.

Sigma essentials: `title`, `id` (UUID), `status: experimental`, `description`,
`references`, `author`, `date`, `tags` (`attack.t1110.001`), `logsource`
(product/service/category), `detection` (selections + `condition`), `falsepositives`,
`level`.

Wazuh mapping notes:
- Custom rules live in `local_rules.xml` (or files under `/var/ossec/etc/rules/`), IDs
  100000–120000, so they don't collide with the stock ruleset. Write them as
  `custom rule 100210` in findings.
- Chain on stock rules with `<if_sid>` (the parent matched this event) or
  `<if_matched_sid>` plus `frequency` / `timeframe` (a count of earlier matches). Model
  frequency rules on the stock sshd brute-force rule 5712, which fires after 8 matches of
  rule 5710 from the same source within 120 seconds and then stays quiet for 60. As a
  custom rule 100210 that reads:
  ```xml
  <rule id="100210" level="10" frequency="8" timeframe="120" ignore="60">
    <if_matched_sid>PARENT_SID</if_matched_sid>
    <same_source_ip />
    <description>...</description>
  </rule>
  ```
  Other correlation options in the stock ruleset: `<same_user />`, `<same_field>`,
  `<if_matched_group>`.
- Map Sigma fields to decoded Wazuh fields (`data.win.eventdata.commandLine`,
  `data.win.system.eventID`, `data.srcip`, `data.dstuser`) with `<field name="...">`
  PCRE2 or OS_Regex patterns. Field names drop the `data.` prefix inside rules
  (`<field name="win.eventdata.commandLine">`).
- Add `<mitre><id>T1110.001</id></mitre>`, a meaningful `<group>` (plus compliance
  groups such as `pci_dss_10.2.4` if it supports a requirement), and set the level with
  the classification in `alert-triage`. Level 12+ pages people.
- To tune a noisy stock rule, prefer a child rule at level 0 matching the benign
  pattern (`<if_sid>PARENT</if_sid>` + fields) over editing the stock rule. Changes to
  stock files are lost on upgrade.
- Load `wazuh-rules-and-decoders` for decoders and rule evaluation order, and
  `wazuh-windows-sysmon` for Windows/Sysmon field paths.

## Backtesting

1. Express the logic as a search over history: `search_security_events` /
   `get_wazuh_alerts` (30 days where possible).
2. Report: expected fire count per day, top triggering hosts/users, how many hits map to
   known incidents (true positives) vs. benign.
3. Target: < 5 alerts/day per rule unless it is a high-fidelity critical rule; FP rate
   estimate stated explicitly.

## FP tuning

Prefer narrowing by behaviour (parent process, command-line pattern, frequency) over
broad allowlists. Every exclusion documents who/what is excluded and why; never
exclude by a value an attacker controls easily (e.g. username alone).

## Coverage

Use `get_wazuh_rules_summary` and existing alert data to note which ATT&CK techniques the
environment already detects; state how the proposal changes coverage.

## Output

- `propose_detection(title, rule_format="sigma"|"wazuh_xml", rule_body, rationale, mitre)`
  where `rationale` contains the ADS sections and backtest results.
- `add_finding` on the originating case titled `Detection proposal: <title>`, or
  `save_report(kind="detection", ...)` for batch reviews. standard_refs:
  `SIGMA`, `MITRE-ATTACK:<id>`, `NIST-CSF-2:DE.CM`.
