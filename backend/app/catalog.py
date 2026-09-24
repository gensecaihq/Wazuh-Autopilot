"""Response action catalog: maps platform action types to Wazuh MCP tools.

Tool names and argument names follow gensecaihq/Wazuh-MCP-Server v4.3.0.
"""

ACTIONS = [
    {"type": "block_ip", "label": "Block IP", "mcp_tool": "wazuh_block_ip",
     "verify_tool": "wazuh_check_blocked_ip", "rollback_tool": "wazuh_firewall_allow",
     "risk": "low", "reversible": True, "d3fend": "D3-ITF",
     "description": "Drop inbound traffic from an IP on one agent or fleet-wide (stock firewall-drop). Permanent until "
                    "rolled back; rollback needs the operator's firewall undo script (WAZUH_AR_FIREWALL_UNDO_COMMAND)."},
    {"type": "firewall_drop", "label": "Firewall drop", "mcp_tool": "wazuh_firewall_drop",
     "verify_tool": "wazuh_check_blocked_ip", "rollback_tool": "wazuh_firewall_allow",
     "risk": "low", "reversible": True, "d3fend": "D3-ITF",
     "description": "Add a firewall drop rule for a source IP on one agent (stock firewall-drop). Permanent until rolled back."},
    {"type": "host_deny", "label": "Host deny", "mcp_tool": "wazuh_host_deny",
     "verify_tool": "wazuh_check_blocked_ip", "rollback_tool": "wazuh_host_allow",
     "risk": "low", "reversible": True, "d3fend": "D3-ITF",
     "description": "Add the IP to /etc/hosts.deny on a Linux agent (stock host-deny)."},
    {"type": "isolate_host", "custom_script": True, "label": "Isolate host", "mcp_tool": "wazuh_isolate_host",
     "verify_tool": "wazuh_check_agent_isolation", "rollback_tool": "wazuh_unisolate_host",
     "risk": "high", "reversible": True, "d3fend": "D3-NI",
     "description": "Cut an endpoint off the network except for the Wazuh manager. Requires a custom host-isolation "
                    "active-response script on the agent (not shipped with Wazuh)."},
    {"type": "kill_process", "custom_script": True, "label": "Kill process", "mcp_tool": "wazuh_kill_process",
     "verify_tool": "wazuh_check_process", "rollback_tool": None,
     "risk": "medium", "reversible": False, "d3fend": "D3-PT",
     "description": "Terminate a process by PID. Requires a custom kill-process active-response script on the agent "
                    "(not shipped with Wazuh)."},
    {"type": "disable_user", "label": "Disable user", "mcp_tool": "wazuh_disable_user",
     "verify_tool": "wazuh_check_user_status", "rollback_tool": "wazuh_enable_user",
     "risk": "high", "reversible": True, "d3fend": "D3-AL",
     "description": "Lock a local user account on an agent (stock disable-account)."},
    {"type": "quarantine_file", "custom_script": True, "label": "Quarantine file", "mcp_tool": "wazuh_quarantine_file",
     "verify_tool": "wazuh_check_file_quarantine", "rollback_tool": "wazuh_restore_file",
     "risk": "medium", "reversible": True, "d3fend": "D3-FEV",
     "description": "Move a file into quarantine. Requires a custom quarantine active-response script on the agent "
                    "(not shipped with Wazuh)."},
    {"type": "active_response", "label": "Custom active response", "mcp_tool": "wazuh_active_response",
     "verify_tool": None, "rollback_tool": None,
     "risk": "critical", "reversible": False, "d3fend": "",
     "description": "Run an arbitrary active-response command on an agent. Always requires a human."},
    {"type": "restart_wazuh", "label": "Restart Wazuh", "mcp_tool": "wazuh_restart",
     "verify_tool": None, "rollback_tool": None,
     "risk": "medium", "reversible": True, "d3fend": "",
     "description": "Restart the Wazuh manager or an agent (e.g. after a config change)."},
]

ACTIONS_BY_TYPE = {a["type"]: a for a in ACTIONS}

# Per-action defaults for the autonomy policy.
DEFAULT_ACTION_RULES = [
    {"type": "block_ip", "autonomy": "inherit", "min_confidence": 0.85, "max_per_hour": 20, "enabled": True},
    {"type": "firewall_drop", "autonomy": "inherit", "min_confidence": 0.85, "max_per_hour": 20, "enabled": True},
    {"type": "host_deny", "autonomy": "inherit", "min_confidence": 0.85, "max_per_hour": 20, "enabled": True},
    {"type": "isolate_host", "autonomy": "supervised", "min_confidence": 0.9, "max_per_hour": 3, "enabled": True},
    {"type": "kill_process", "autonomy": "inherit", "min_confidence": 0.9, "max_per_hour": 10, "enabled": True},
    {"type": "disable_user", "autonomy": "supervised", "min_confidence": 0.9, "max_per_hour": 5, "enabled": True},
    {"type": "quarantine_file", "autonomy": "inherit", "min_confidence": 0.85, "max_per_hour": 10, "enabled": True},
    {"type": "active_response", "autonomy": "manual", "min_confidence": 0.95, "max_per_hour": 2, "enabled": False},
    {"type": "restart_wazuh", "autonomy": "manual", "min_confidence": 0.9, "max_per_hour": 2, "enabled": True},
]


def mcp_arguments(action_type: str, target: str, params: dict) -> dict:
    """Build Wazuh MCP tool arguments for an action (v4.3.0 input schemas)."""
    p = dict(params or {})
    agent_id = p.get("agent_id")
    if action_type == "block_ip":
        args = {"ip_address": p.get("ip_address") or target}
        if agent_id:
            args["agent_id"] = agent_id
        else:
            args["all_agents"] = True  # the server refuses a block with neither
    elif action_type in {"firewall_drop", "host_deny"}:
        args = {"agent_id": agent_id, "src_ip": p.get("src_ip") or p.get("ip_address") or target}
    elif action_type == "isolate_host":
        args = {"agent_id": agent_id or target}
    elif action_type == "kill_process":
        args = {"agent_id": agent_id, "process_id": str(p.get("process_id") or p.get("pid") or target)}
    elif action_type == "disable_user":
        args = {"agent_id": agent_id, "username": p.get("username") or target}
    elif action_type == "quarantine_file":
        args = {"agent_id": agent_id, "file_path": p.get("file_path") or target}
    elif action_type == "active_response":
        args = {"agent_id": agent_id, "command": p.get("command") or target}
        if p.get("parameters") or p.get("arguments"):
            args["parameters"] = p.get("parameters") or p.get("arguments")
    elif action_type == "restart_wazuh":
        args = {"target": agent_id or target or "manager"}
    else:
        raise ValueError(f"unknown action type {action_type}")
    return {k: v for k, v in args.items() if v is not None}


def missing_arguments(action_type: str, args: dict) -> list[str]:
    required = {
        "block_ip": ["ip_address"], "firewall_drop": ["agent_id", "src_ip"], "host_deny": ["agent_id", "src_ip"],
        "isolate_host": ["agent_id"], "kill_process": ["agent_id", "process_id"],
        "disable_user": ["agent_id", "username"], "quarantine_file": ["agent_id", "file_path"],
        "active_response": ["agent_id", "command"], "restart_wazuh": ["target"],
    }
    return [k for k in required.get(action_type, []) if not args.get(k)]


def verify_arguments(action_type: str, args: dict) -> dict | None:
    """Arguments for the verification tool, or None if the action has none."""
    ip = args.get("ip_address") or args.get("src_ip")
    if action_type in {"block_ip", "firewall_drop", "host_deny"}:
        out = {"ip_address": ip}
        if args.get("agent_id"):
            out["agent_id"] = args["agent_id"]
        return out
    if action_type == "isolate_host":
        return {"agent_id": args["agent_id"]}
    if action_type == "kill_process":
        return {"agent_id": args["agent_id"], "process_id": args["process_id"]}
    if action_type == "disable_user":
        return {"agent_id": args["agent_id"], "username": args["username"]}
    if action_type == "quarantine_file":
        return {"agent_id": args["agent_id"], "file_path": args["file_path"]}
    return None


def rollback_arguments(action_type: str, args: dict) -> dict | None:
    """Arguments for the rollback tool, or None if the action can't be rolled back as executed."""
    if action_type in {"block_ip", "firewall_drop", "host_deny"}:
        if not args.get("agent_id"):
            return None  # fleet-wide blocks have to be undone per agent
        return {"agent_id": args["agent_id"], "src_ip": args.get("ip_address") or args.get("src_ip")}
    if action_type == "isolate_host":
        return {"agent_id": args["agent_id"]}
    if action_type == "disable_user":
        return {"agent_id": args["agent_id"], "username": args["username"]}
    if action_type == "quarantine_file":
        return {"agent_id": args["agent_id"], "file_path": args["file_path"]}
    return None
