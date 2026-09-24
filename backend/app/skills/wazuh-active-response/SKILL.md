---
name: wazuh-active-response
description: How Wazuh active response actually works — commands, agent-side scripts, dispatch vs execution, permanence, blast radius, pre-checks and verification caveats — for planning and verifying containment; use before proposing or verifying any response action.
allowed-tools: check_agent_health get_agent_processes get_wazuh_agents get_wazuh_alerts wazuh_check_blocked_ip wazuh_check_agent_isolation wazuh_check_process wazuh_check_user_status wazuh_check_file_quarantine get_case search_cases list_actions update_case add_entities add_finding link_mitre
metadata:
  category: response
  display_name: Wazuh Active Response
  standards: [mitre-d3fend, nist-800-61r3, sans-picerl, nist-800-53r5]
  version: "1.0"
---
# Wazuh Active Response

Agents never execute actions. The response-planner proposes (`propose_action`); the autonomy policy and
human approvers decide; the platform executor calls the Wazuh MCP action tool; the responder verifies.
This skill explains what happens underneath so plans are realistic and verification is honest.

## How Wazuh AR works

1. The Wazuh API (via the MCP server) sends an active-response **command** to one or more agents.
2. The **agent** runs a script of that name from its active-response bin directory. If the script
   isn't deployed on that agent, nothing happens on the host.
3. The API returns as soon as the manager **accepts and dispatches** the command
   ("AR command was sent to the agent") — this is **not** proof of execution.
4. The script logs its outcome; Wazuh turns that log into an alert in the `active_response` group.
5. **API-triggered AR is permanent**: Wazuh ignores the timeout for API-triggered commands, so a block
   stays until explicitly removed (rollback), unlike rule-triggered AR with a timeout.

## What each platform action sends

| Platform action | MCP tool | AR command | Stock script? | Rollback |
|---|---|---|---|---|
| block_ip | wazuh_block_ip | `!firewall-drop` (`-srcip`) on one agent or `all_agents` | Yes | wazuh_firewall_allow — per agent; needs an undo script configured on the MCP server |
| firewall_drop | wazuh_firewall_drop | `!firewall-drop` | Yes | wazuh_firewall_allow |
| host_deny | wazuh_host_deny | `!host-deny` (adds to `/etc/hosts.deny`, Linux) | Yes | wazuh_host_allow |
| disable_user | wazuh_disable_user | `!disable-account` | Yes (Linux) | wazuh_enable_user |
| isolate_host | wazuh_isolate_host | `!host-isolation` | **No — custom script required** | wazuh_unisolate_host |
| kill_process | wazuh_kill_process | `!kill-process` (PID) | **No — custom script required** | None |
| quarantine_file | wazuh_quarantine_file | `!quarantine` (path) | **No — custom script required** | wazuh_restore_file |
| restart_wazuh | wazuh_restart | Wazuh API restart of agent or manager | n/a | n/a |
| active_response | wazuh_active_response | Allowlisted command names only | Depends | Depends |

If the org hasn't deployed the custom scripts, isolate/kill/quarantine will be "dispatched" and do
nothing. Say so in the plan and prefer actions with stock scripts, or recommend a manual step.

## Blast radius

- `block_ip` with no agent means `all_agents=true`: fleet-wide and permanent. Name the agents that
  actually see the attacker (from the alerts) instead, unless the IP is confirmed malicious and
  internet-only. Fleet-wide blocks can only be rolled back agent by agent.
- Never target the manager (agent `000`) — the MCP server refuses it by default.
- Protected targets (policy) are refused before execution; don't propose them.
- Isolation cuts the host off except for the manager: confirm the business owner impact first.

## Pre-checks (responder and response-planner)

1. Agent connected? `check_agent_health agent_id="<id>"` — AR to a disconnected agent is queued or lost.
2. Already done? `wazuh_check_blocked_ip` / `wazuh_check_agent_isolation` / `wazuh_check_user_status`
   before proposing a duplicate.
3. Target still valid? For kill_process, confirm the PID with `get_agent_processes` (syscollector is a
   periodic inventory — PIDs can be stale or reused).
4. Evidence preserved? Kill and quarantine destroy volatile evidence — record process details first.

## Verification caveats

The `wazuh_check_*` tools **infer** state; they are not live host queries:

| Check | Evidence it uses |
|---|---|
| wazuh_check_blocked_ip | AR alert history in the `active_response` group for that IP — e.g. rule 601 (level 3, "Host Blocked by firewall-drop Active Response") or its JSON-log equivalent rule 651 (level 3); host-deny: rule 603 / rule 653 (level 3) |
| wazuh_check_agent_isolation | Agent connectivity plus AR history mentioning isolation |
| wazuh_check_process | Syscollector process inventory (periodic) — a killed PID can still appear until the next scan; read `inventory_scan_time` |
| wazuh_check_user_status | AR history mentioning the username |
| wazuh_check_file_quarantine | A FIM "File deleted" alert — rule 553 (level 7) — for the exact path |

Unblock evidence: rule 602 / rule 652 (level 3, "Host Unblocked by firewall-drop Active Response").
rule 658 (level 5) means the AR was activated but may not have had an effect — treat as **not verified**.
No AR alert at all usually means the script didn't run (missing script, agent offline, AR disabled).

Report verification as verified / not verified / inconclusive with the evidence, never as "done"
because the API said so.

## Roles

- **response-planner**: pick the least destructive action that contains the threat, order it
  (evidence → contain → eradicate), include rollback and blast radius in the rationale, then propose.
  Hand off to responder only via the platform (verification runs automatically after execution).
- **responder**: run the matching `wazuh_check_*`, look for the AR alerts above, record the finding,
  and if something went wrong recommend rollback — hand off to response-planner for any new action.

## Output

`add_finding` with action, target agent(s), AR command, stock/custom script status, pre-check results,
verification evidence (rule and timestamp) and rollback path; refs such as `MITRE-D3FEND:D3-ITF`,
`NIST-800-61r3:Respond`.
