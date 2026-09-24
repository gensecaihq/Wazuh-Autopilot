---
name: containment-playbooks
description: Reference for every Wazuh containment action type — when to use it, required parameters, D3FEND mapping, verification and rollback tools; use when proposing, reviewing or verifying a specific response action.
allowed-tools: get_case list_actions get_wazuh_agents check_agent_health get_agent_processes wazuh_check_blocked_ip wazuh_check_agent_isolation wazuh_check_process wazuh_check_user_status wazuh_check_file_quarantine add_finding handoff_to_agent
metadata:
  category: response
  display_name: Containment Playbooks
  standards: [mitre-d3fend, nist-800-61r3, sans-picerl, nist-csf-2]
  version: "1.1"
---
# Containment Playbooks

The `response-planner` proposes these actions with `propose_action`. Any other agent
holding this skill (e.g. `responder`) hands off to `response-planner` instead. The
platform executor runs the Wazuh MCP tool only after policy and approval. No agent can call
the executor tools listed below. Parameters must match what the executor expects or
execution fails. Load `wazuh-active-response` for how Wazuh AR scripts, timeouts and
agent-side requirements work.

## Action reference

| Type | Executor tool (not callable by agents) | `params` for propose_action | Verify (read-only) | Rollback | D3FEND |
|---|---|---|---|---|---|
| block_ip | wazuh_block_ip | `ip_address` + (`agent_id`, or none for fleet-wide) | wazuh_check_blocked_ip | wazuh_firewall_allow (per agent only) | D3-ITF Inbound Traffic Filtering |
| firewall_drop | wazuh_firewall_drop | `ip_address` (sent as `src_ip`), `agent_id` | wazuh_check_blocked_ip | wazuh_firewall_allow | D3-ITF Inbound Traffic Filtering |
| host_deny | wazuh_host_deny | `ip_address` (sent as `src_ip`), `agent_id` | wazuh_check_blocked_ip | wazuh_host_allow | D3-ITF Inbound Traffic Filtering |
| isolate_host | wazuh_isolate_host | `agent_id` | wazuh_check_agent_isolation | wazuh_unisolate_host | D3-NI Network Isolation |
| kill_process | wazuh_kill_process | `agent_id` + `process_id` (a PID; names are not accepted) | wazuh_check_process | none (process gone) | D3-PT Process Termination |
| disable_user | wazuh_disable_user | `agent_id`, `username` | wazuh_check_user_status | wazuh_enable_user | D3-AL Account Locking |
| quarantine_file | wazuh_quarantine_file | `agent_id`, `file_path` | wazuh_check_file_quarantine | wazuh_restore_file | D3-FEV File Eviction |
| active_response | wazuh_active_response | `agent_id`, `command` (+ `parameters`) | depends on command | depends on command | none |
| restart_wazuh | wazuh_restart | `agent_id`, or `target: "manager"` | check_agent_health | none | none |

Before proposing, check the current state with the read-only tools: is the IP already
blocked (`wazuh_check_blocked_ip`)? Is the agent connected (`check_agent_health`)? A
disconnected agent can't run AR, so propose nothing it can't execute. Say so and escalate.

Outbound C2 blocking maps to D3-OTF Outbound Traffic Filtering; say so in the rationale
when the blocked IP is a C2 destination rather than an inbound attacker.

## When to use

**block_ip** — external attacker IP (brute force, exploitation, scanning with success
risk). Through the Wazuh MCP Server the block is **permanent until removed**: there is
no timeout. Undoing it needs `wazuh_firewall_allow` per agent plus an undo script the
operator has deployed. Put the intended review time in the rationale. Omitting
`agent_id` blocks fleet-wide, which can't be rolled back automatically, so prefer the
affected agent unless the whole internet-facing fleet is under attack. Never block
internal infrastructure IPs (DNS, proxies, NAT gateways): it blocks everyone behind them.
Beware shared cloud/CDN IPs.

**firewall_drop / host_deny** — same intent as block_ip on a specific agent; host_deny
uses TCP wrappers (`/etc/hosts.deny`) and affects only wrapper-aware services (e.g.
sshd builds with libwrap). Prefer block_ip unless policy requires these.

**isolate_host** — confirmed compromise with active attacker, lateral movement or C2.
Cuts the host off except for the Wazuh manager. High business impact on servers —
state the service impact. Capture evidence first (host-forensics finding).

**kill_process** — single malicious process (miner, reverse shell) on an otherwise
healthy host. Evidence first: record PID, path, command line, parent, hash from
`get_agent_processes` (syscollector inventory, so confirm the PID is current). Malware
may respawn: pair with persistence removal (human step) or isolation.

**disable_user** — account confirmed used maliciously. Note whether it's a service /
break-glass account and the impact. Credential reset and session revocation are human
recovery steps.

**quarantine_file** — malicious file on disk (web shell, dropped binary). Include the
hash in the rationale. Quarantine, never delete.

**active_response** — custom AR scripts deployed by the operator. Use only when the
command name is known to exist in the environment; otherwise don't propose. The default
autonomy policy disables this type, so expect a refusal unless an admin enabled it.

**restart_wazuh** — agent misbehaving (not collecting, stuck), never as a security
containment step. Low security value, may lose volatile context.

## Rationale checklist

1. Evidence (alert ids, finding titles).
2. Why this action and not a less disruptive one.
3. Business impact and blast radius.
4. Dependencies / ordering.
5. Rollback path and verification tool.

## Output

- `response-planner`: `propose_action` with exact params above. Others: hand off to
  `response-planner` with the proposed action spelled out.
- For reviews, `add_finding` titled `Containment review` noting parameter problems,
  protected-target conflicts, or missing rollback paths. standard_refs:
  `MITRE-D3FEND:<id>`, `NIST-CSF-2:RS.MI`.
