# Agents, Skills and Workflows

## Roster

| Agent (id) | Codename | Role | Key skills |
|---|---|---|---|
| SOC Commander (`commander`) | Overwatch | Swarm entry point for open-ended sweeps; routes work | swarm-coordination |
| Tier 1 Triage (`triage`) | Sentinel | Validates alerts, scores severity, extracts entities, opens or attaches cases | alert-triage, severity-scoring, entity-extraction |
| Tier 2 Correlation (`correlation`) | Weaver | Correlates activity by entity and time, maps to ATT&CK, builds the timeline | alert-correlation, mitre-attack-mapping, incident-timeline |
| Tier 3 DFIR (`investigation`) | Sleuth | Host and identity forensics, blast radius | host-forensics, identity-compromise, 6 IR playbooks |
| CTI Analyst (`threat-intel`) | Oracle | Indicator enrichment, source grading, attribution | ioc-enrichment, threat-actor-attribution |
| Threat Hunter (`threat-hunter`) | Tracker | Hypothesis-driven hunts (PEAK) | threat-hunting |
| Vulnerability Manager (`vuln-management`) | Patchwork | KEV → EPSS → CVSS → SSVC prioritization | vulnerability-prioritization, ir-playbook-vulnerability-spike |
| IR Lead (`response-planner`) | Strategist | Containment plan; the only agent with `propose_action` | response-planning, containment-playbooks, all 7 IR playbooks |
| SecOps Engineer (`responder`) | Enforcer | Verifies executed actions on the endpoint | action-verification |
| Detection Engineer (`detection-engineer`) | Forge | Sigma / Wazuh rule proposals (never auto-deployed) | detection-engineering |
| GRC Analyst (`compliance`) | Auditor | PCI DSS, ISO 27001, NIST 800-53, CIS evidence | compliance-mapping |
| Wazuh Platform Engineer (`platform-engineer`) | Keeper | Agent connectivity, manager/cluster health, dropped events, silent log sources (detection blind spots) | wazuh-platform-health, wazuh-rules-and-decoders |
| SOC Manager (`reporting`) | Chronicle | Incident, daily and executive reports, SOC metrics | executive-reporting, soc-metrics |

Every agent also carries `prompt-injection-defense` and `wazuh-mcp-querying`, and the detection and investigation agents carry the Wazuh domain skills below. Each agent's **Config** tab lets you enable or disable it, override its model, cap its autonomy, change its skills and add organization-specific guidance. The **Prompt** tab shows the exact system prompt, skills and tools it receives.

### Tools

Agents get only the tools listed in their roster entry:

- **Wazuh MCP read tools**, e.g. `get_wazuh_alerts`, `search_security_events`, `get_agent_processes`, `check_ioc_reputation`, `get_wazuh_critical_vulnerabilities`, `run_compliance_check`.
- **Verification tools** (`wazuh_check_*`, read-only state checks) for the DFIR investigator, IR lead and SecOps engineer.
- **Platform tools**: `get_case`, `search_cases`, `create_case`, `update_case`, `add_entities`, `link_mitre`, `add_finding`, `propose_action`, `list_actions`, `save_report`, `propose_detection`.
- **`skills`** (load a skill) and, in swarm workflows, **`handoff_to_agent`**.

No agent ever holds a state-changing `wazuh_*` tool. See [AUTONOMY_AND_APPROVALS.md](AUTONOMY_AND_APPROVALS.md).

## Skills

Skills follow the [Agent Skills](https://agentskills.io) `SKILL.md` format and load through Strands' `AgentSkills` plugin. Each skill's name and description sit in the agent's prompt, and the full procedure is loaded only when the agent calls `skills`. That keeps prompts small and lets one agent carry many procedures.

| Category | Skills |
|---|---|
| Command / safety | swarm-coordination, prompt-injection-defense |
| Detection | alert-triage, severity-scoring, entity-extraction, alert-correlation, mitre-attack-mapping, threat-hunting, detection-engineering |
| Investigation | incident-timeline, host-forensics, identity-compromise |
| Intel | ioc-enrichment, threat-actor-attribution |
| Vulnerability | vulnerability-prioritization |
| Response | response-planning, containment-playbooks, action-verification |
| IR playbooks | ir-playbook-bruteforce, -lateral-movement, -privilege-escalation, -ransomware, -suspicious-powershell, -data-exfiltration, -vulnerability-spike |
| Compliance / reporting | compliance-mapping, executive-reporting, soc-metrics |
| Wazuh | wazuh-mcp-querying, wazuh-rules-and-decoders, wazuh-fim-investigation, wazuh-sca-hardening, wazuh-malware-detection, wazuh-windows-sysmon, wazuh-cloud-container, wazuh-active-response, wazuh-platform-health |

Built-ins live in `backend/app/skills/<id>/SKILL.md`. Every Wazuh rule ID a skill cites (written as `rule 5712` / `rules 5710, 5712`) is checked against the official Wazuh 4.14 ruleset: `backend/tests/data/wazuh_rule_refs.json` is regenerated with `backend/scripts/build_wazuh_rule_refs.py`, and `test_wazuh_skills.py` fails on unknown IDs or wrong levels. Tests also require that a skill's `allowed-tools` are held by every agent carrying it. Behaviors the stock ruleset doesn't detect (password spraying, ransomware mass changes, DNS tunneling, etc.) are documented in the playbooks as `custom rule 1000xx` sketches you create in `local_rules.xml`. The IR playbooks include the full playbook as `references/playbook.md`. Custom skills and edits to built-ins are managed in **Skills Library** and stored in the database.

## Standards

Agents and skills are mapped to NIST CSF 2.0, NIST SP 800-61r3, NIST SP 800-53r5, MITRE ATT&CK v17, MITRE D3FEND, CIS Controls v8.1, ISO/IEC 27001:2022, PCI DSS v4.0.1, SANS PICERL, CISA KEV, FIRST EPSS, CISA SSVC, Sigma and the OWASP Top 10 for LLM Applications. Findings cite them in `standard_refs`, and **Standards** shows coverage and evidence per framework.

## Workflows

| Workflow | Mode | Trigger | Agents |
|---|---|---|---|
| Alert → Containment | swarm | high/critical incident | triage → correlation → investigation → threat-intel → response-planner (→ detection-engineer, reporting) |
| Alert triage (fast lane) | graph | medium incident | triage → correlation |
| Post-action verification | graph | action executed | responder |
| Scheduled threat hunt | graph | every 6h | threat-hunter → detection-engineer |
| Vulnerability sweep | graph | daily 07:00 UTC | vuln-management → reporting |
| Compliance audit | graph | Mondays 06:00 UTC | compliance → reporting |
| Daily SOC briefing | graph | daily 08:00 UTC | reporting |
| Wazuh platform health | graph | every 4h | platform-engineer |
| Commander sweep | swarm | manual | commander → specialists |

In **swarm** mode the entry agent starts, and agents call `handoff_to_agent` along the allowed edges. The run is bounded by max handoffs, max iterations, run and per-agent timeouts, and repetitive-handoff detection (**Settings → Swarm limits**). In **graph** mode each agent's output feeds the next. Workflows can be enabled, disabled, re-triggered and edited in **Workflows**.

## Evals

**Evals** runs `strands-agents-evals` suites in dry-run mode: nothing is written to cases, actions or reports. The built-in suites check triage fundamentals (including prompt injection hidden in alert fields), response-planning safety (proposals only through `propose_action`), and KEV-first vulnerability prioritization. Run them after changing a model, skill or prompt.
