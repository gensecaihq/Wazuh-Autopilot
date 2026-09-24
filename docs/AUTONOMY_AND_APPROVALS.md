# Autonomy, Approvals and Execution

Agents never act on Wazuh directly. They call `propose_action`, the policy engine decides what happens, and only the platform executor runs MCP action tools.

## Autonomy levels

| Level | What happens to a proposal |
|---|---|
| **Observe** | Refused. Agents analyze and document only. |
| **Recommend** | Queued. A human approves (Tier 1) **and** executes (Tier 2). Default for new installs. |
| **Supervised** | Queued. A human approves, and the platform executes immediately. |
| **Autonomous** | Executes automatically if the action's rule allows it, confidence ≥ the rule's floor, the hourly budget isn't spent, the target isn't protected, and the action isn't critical risk. Otherwise it falls back to supervised. |

Set the global level in **Autonomy Policy**. Two more controls narrow it:

- **Per-action rules**: each action type can inherit the global level or be pinned to manual, supervised or autonomous, with a confidence floor, an hourly auto-execution budget and an enabled flag. Defaults pin `isolate_host` and `disable_user` to supervised, `restart_wazuh` to manual, and disable `active_response`.
- **Agent autonomy cap**: an agent's proposals never get more autonomy than its cap (agent **Config** tab).

Also available:

- **Protected targets**: IPs/CIDRs, hostnames, usernames and Wazuh agent IDs that are refused outright (default: `127.0.0.1`, `dc-01`, `wazuh-manager`, `root`, `Administrator`, agent `000`).
- **Two-person rule**: the approver can't also execute.
- **Business hours only**: autonomous execution is limited to weekdays 08:00–18:00 UTC.
- **Approval expiry**: unanswered proposals expire (default 60 minutes).

## Action catalog

| Type | MCP tool | Verification | Rollback | Risk | D3FEND |
|---|---|---|---|---|---|
| block_ip | wazuh_block_ip | wazuh_check_blocked_ip | wazuh_firewall_allow (per agent) | low | D3-ITF |
| firewall_drop | wazuh_firewall_drop | wazuh_check_blocked_ip | wazuh_firewall_allow | low | D3-ITF |
| host_deny | wazuh_host_deny | wazuh_check_blocked_ip | wazuh_host_allow | low | D3-ITF |
| isolate_host | wazuh_isolate_host | wazuh_check_agent_isolation | wazuh_unisolate_host | high | D3-NI |
| kill_process | wazuh_kill_process | wazuh_check_process | none | medium | D3-PT |
| disable_user | wazuh_disable_user | wazuh_check_user_status | wazuh_enable_user | high | D3-AL |
| quarantine_file | wazuh_quarantine_file | wazuh_check_file_quarantine | wazuh_restore_file | medium | D3-FEV |
| active_response | wazuh_active_response | none | none | critical | none |
| restart_wazuh | wazuh_restart | none | none | medium | none |

**Agent-side scripts.** `block_ip`, `firewall_drop`, `host_deny`, `disable_user` and `restart_wazuh` use stock Wazuh active-response scripts. `isolate_host`, `kill_process` and `quarantine_file` send `!host-isolation`, `!kill-process` and `!quarantine`, which don't ship with Wazuh: deploy those scripts on your agents before enabling these actions, or execution fails. IP blocks triggered through the API are permanent until rolled back, and rolling back a firewall block needs the undo script configured on the MCP server (`WAZUH_AR_FIREWALL_UNDO_COMMAND`).

Arguments follow the Wazuh MCP Server v4.3.0 schemas (for example `firewall_drop` takes `agent_id` + `src_ip`, and `restart_wazuh` takes `target`). The executor checks required arguments before calling the tool.

## Approvals

**Approvals** lists pending proposals with the case, the proposing agent, confidence, rationale, parameters and time to expiry. Approving needs `actions:approve` (Incident Responder, SOC Manager, Administrator). Executing and rolling back need `actions:execute`. Rejections need a reason. Every decision goes into the audit log and the case timeline, and Slack can notify on `approval_needed` and `action_failed`.

## Execution and verification

1. The executor calls the action's MCP tool with the Wazuh-shaped arguments. This needs the `wazuh:write` scope on the MCP key.
2. Wazuh's success response means the command was accepted for dispatch, not that it ran on the host. So the executor calls the matching `wazuh_check_*` tool and marks the action `verified` only when the check confirms it. Otherwise it stays `executed` with the check's note. The check tools infer state from active-response alert history, FIM deletion alerts and syscollector inventory; they don't query the host live, so a fresh action may read as unconfirmed until those events arrive.
3. The Responder agent's post-action workflow records its own verification finding and recommends rollback if something looks wrong.
4. **Rollback** runs the inverse tool where one exists. Fleet-wide IP blocks have to be undone per agent.

