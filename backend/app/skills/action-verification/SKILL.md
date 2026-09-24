---
name: action-verification
description: Verify on-host effect of executed containment actions with the wazuh_check_* tools, record verified/failed/unknown, and recommend rollback or retry; use after the platform reports an action executed.
allowed-tools: get_case list_actions wazuh_check_blocked_ip wazuh_check_agent_isolation wazuh_check_process wazuh_check_user_status wazuh_check_file_quarantine check_agent_health get_wazuh_alerts get_agent_processes add_finding update_case handoff_to_agent
metadata:
  category: response
  display_name: Action Verification
  standards: [nist-800-61r3, nist-csf-2, mitre-d3fend]
  version: "1.1"
---
# Action Verification

A successful Wazuh API call means the active-response command was **dispatched**, not
that it worked on the host. The agent may be disconnected, the AR script missing, or
the attacker may have re-established access. Verify every executed action.

## Procedure

1. `list_actions(case_id)` — find actions with status `executed` (or `verified: null`).
2. For each, call the matching check tool with the same target parameters. Know what each
   check actually looks at. None of them read live host state, so treat a positive as strong
   evidence, not proof:

| Action type | Check tool | What it inspects (Wazuh MCP Server v4.3.0) | Verified when |
|---|---|---|---|
| block_ip / firewall_drop / host_deny | `wazuh_check_blocked_ip(ip_address, agent_id)` | active-response alerts (`rule.groups: active_response`) with `data.srcip` = IP in the last 24h, e.g. rule 651 "Host Blocked by firewall-drop Active Response" or rule 653 (host-deny) | `blocked: true` (`matching_alerts` > 0) |
| isolate_host | `wazuh_check_agent_isolation(agent_id)` | a recent active-response alert mentioning isolation for the agent. Connection status is **not** a signal: an isolated host keeps its manager link | `isolation_confirmed: true` |
| kill_process | `wazuh_check_process(agent_id, process_id)` | syscollector process inventory for that PID. Periodic, not live: compare `inventory_scan_time` to the execution time | `running: false` with a scan time **after** execution |
| disable_user | `wazuh_check_user_status(agent_id, username)` | active-response alerts mentioning the user in the last 24h, classified disable/enable. A heuristic, not order-aware | `likely_disabled: true` |
| quarantine_file | `wazuh_check_file_quarantine(agent_id, file_path)` | the latest FIM "deleted" alert (rule 553) for the exact path. Needs the path under FIM monitoring and the Indexer configured | `quarantined: true` |
| restart_wazuh | `check_agent_health(agent_id)` | agent status and last keepalive | agent active with a keepalive after execution |

   Wazuh writes the AR alerts only after the agent runs the script, so an AR alert
   (rules 651, 653, or rule 657 "Active response: <program> - <command>") is better evidence
   than the API's dispatch acceptance. `null` or "inconclusive" results are common when the Indexer isn't
   configured on the MCP server. Report them as `unknown`, not `failed`. Load
   `wazuh-active-response` for how AR scripts and timeouts behave.
3. If the check is inconclusive, `check_agent_health` — a disconnected agent can't apply
   or report AR; say "unknown", not "failed".
4. Look for **effect** evidence too: `get_wazuh_alerts` after execution time. Did the
   blocked IP keep generating alerts (for example more rule 5710 from the same `data.srcip`)?
   Did the killed process reappear in `get_agent_processes`? A block that was undone shows
   up as rule 652 "Host Unblocked by firewall-drop Active Response", usually from an AR timeout.
5. Wait-and-recheck guidance: AR is asynchronous; if the first check is negative within
   2 minutes of execution, report `pending` and recommend a re-check rather than failure.

## Outcomes

| Outcome | Criteria | Recommendation |
|---|---|---|
| verified | check positive and no continued attacker activity | case can move toward `contained` |
| partial | check positive but attacker activity continues (other IPs, other hosts) | hand off to `response-planner` for additional containment |
| failed | check negative after re-check, agent healthy | retry once; if still failing, escalate to a human (AR script missing?) |
| unknown | agent disconnected / check tool errored | escalate; don't mark contained |

## Dry-run and demo runs

If the action was executed in dry-run mode, the check tools reflect the real host, so a
negative result is expected. Report `not applicable (dry run)` instead of `failed`.

## Harm check

If the action caused business impact (service down, legitimate users blocked — look
for new alerts or human comments), recommend rollback with the rollback tool named in
`containment-playbooks`. Rollback itself is a human-approved action.

## Output

- `add_finding` titled `Verification: <action type> <target>` with check tool, raw
  result summary, timestamps, outcome, and recommendation. standard_refs:
  `NIST-800-61r3`, `NIST-CSF-2:RS.MI`.
- `update_case(status="contained")` only when all containment actions for the case are
  `verified`.
