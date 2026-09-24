"""Role-based access control: roles, permissions, and the FastAPI dependency."""

ALL_PERMISSIONS = [
    "dashboard:read", "alerts:read", "alerts:ingest", "cases:read", "cases:write",
    "actions:read", "actions:propose", "actions:approve", "actions:execute",
    "agents:read", "agents:write", "skills:read", "skills:write",
    "workflows:read", "workflows:write", "workflows:run", "runs:read", "runs:debug",
    "playground:use", "evals:read", "evals:run", "standards:read",
    "policy:read", "policy:write", "settings:read", "settings:write",
    "users:manage", "audit:read",
]

_ANALYST = [
    "dashboard:read", "alerts:read", "cases:read", "cases:write", "actions:read", "actions:propose",
    "agents:read", "skills:read", "workflows:read", "workflows:run", "runs:read", "runs:debug",
    "playground:use", "evals:read", "standards:read",
]

ROLES = {
    "admin": {
        "label": "Administrator",
        "description": "Full control of the platform, users and integrations.",
        "permissions": list(ALL_PERMISSIONS),
    },
    "soc_manager": {
        "label": "SOC Manager",
        "description": "Runs the SOC: swarm configuration, policy, approvals and settings. Cannot manage users.",
        "permissions": [p for p in ALL_PERMISSIONS if p != "users:manage"],
    },
    "responder": {
        "label": "Incident Responder",
        "description": "Analyst access plus approving and executing response actions.",
        "permissions": _ANALYST + ["actions:approve", "actions:execute", "policy:read"],
    },
    "analyst": {
        "label": "SOC Analyst",
        "description": "Works alerts and cases, runs workflows and debugs agents. Cannot approve actions.",
        "permissions": list(_ANALYST),
    },
    "auditor": {
        "label": "Auditor",
        "description": "Read-only access to everything, including the audit log.",
        "permissions": [p for p in ALL_PERMISSIONS if p.endswith(":read")],
    },
}


def permissions_for(role: str) -> list[str]:
    return ROLES.get(role, {}).get("permissions", [])


def has_permission(role: str, permission: str) -> bool:
    return permission in permissions_for(role)
