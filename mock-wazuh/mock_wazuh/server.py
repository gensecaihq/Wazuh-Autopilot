"""Mock Wazuh MCP Server — drop-in stand-in for gensecaihq/Wazuh-MCP-Server v4.3.0.

Endpoints (same as the real server):
  POST /mcp          MCP Streamable HTTP (Bearer token required)
  POST /auth/token   {"api_key": "..."} -> {"access_token", "token_type", "expires_in"}
  GET  /health       {"status": "healthy", ...}
"""

from __future__ import annotations

import asyncio
import collections
import json
import os
import secrets
import threading
import time
from pathlib import Path

import mcp_types as types
import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .sim import Environment, run_generator
from .tools_impl import HANDLERS, OPEN_WORLD_TOOLS, REVERSAL_TOOLS, WRITE_TOOLS, ToolError

VERSION = "4.3.0-mock"
API_KEY = os.getenv("MOCK_API_KEY", "wazuh_demo_key")
API_KEY_SCOPES = os.getenv("MOCK_API_KEY_SCOPES", "wazuh:read wazuh:write").split()
AUTH_MODE = os.getenv("MOCK_AUTH_MODE", "bearer")  # bearer | none
TOKEN_TTL = int(os.getenv("MOCK_TOKEN_TTL", "3600"))

TOOL_DEFS = json.loads((Path(__file__).parent / "tools.json").read_text())
TOOL_BY_NAME = {t["name"]: t for t in TOOL_DEFS}
missing = set(TOOL_BY_NAME) - set(HANDLERS)
assert not missing, f"tools without handlers: {missing}"

ENV = Environment(seed=int(os.getenv("MOCK_SEED", "1337")), backfill_days=int(os.getenv("MOCK_BACKFILL_DAYS", "7")),
                  ring_size=int(os.getenv("MOCK_MAX_ALERTS", "20000")))
_tokens: dict[str, dict] = {}
_tokens_lock = threading.Lock()


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------
def _scopes_for(auth_header: str | None) -> list[str] | None:
    """Scopes for a bearer header, or None when the token is invalid."""
    if AUTH_MODE == "none":
        return ["wazuh:read", "wazuh:write"] if os.getenv("MOCK_AUTHLESS_ALLOW_WRITE", "true") == "true" else ["wazuh:read"]
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if secrets.compare_digest(token, API_KEY):  # raw key accepted too (legacy-rest style clients)
        return API_KEY_SCOPES
    with _tokens_lock:
        info = _tokens.get(token)
        if info and info["exp"] > time.time():
            return info["scopes"]
    return None


async def auth_token(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_request", "detail": "JSON body with api_key required"}, status_code=400)
    key = str(body.get("api_key") or "")
    if not key or not secrets.compare_digest(key, API_KEY):
        return JSONResponse({"error": "invalid_api_key", "detail": "Invalid API key"}, status_code=401)
    token = "mock." + secrets.token_urlsafe(32)
    with _tokens_lock:
        now = time.time()
        for t in [t for t, i in _tokens.items() if i["exp"] < now]:
            _tokens.pop(t, None)
        _tokens[token] = {"scopes": API_KEY_SCOPES, "exp": now + TOKEN_TTL}
    return JSONResponse({"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL, "scope": " ".join(API_KEY_SCOPES)})


async def health(request: Request):
    return JSONResponse({"status": "healthy", "version": VERSION, "mock": True, "alerts_stored": len(ENV.alerts),
                         "uptime_seconds": int(time.time() - ENV.started_at),
                         "active_responses": len(ENV.ar_log)})


class RequireBearer:
    """401 for /mcp requests without a valid bearer token (like the real server)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].rstrip("/") == "/mcp":
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if _scopes_for(headers.get("authorization")) is None:
                resp = JSONResponse({"error": "unauthorized", "detail": "Valid bearer token required (POST /auth/token)"},
                                    status_code=401, headers={"WWW-Authenticate": 'Bearer realm="wazuh-mcp"'})
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _request_scopes(ctx) -> list[str]:
    req = getattr(ctx, "request", None)
    header = req.headers.get("authorization") if req is not None and hasattr(req, "headers") else None
    return _scopes_for(header) or []


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------
def _annotations(name: str) -> types.ToolAnnotations:
    write = name in WRITE_TOOLS
    return types.ToolAnnotations(read_only_hint=not write, destructive_hint=write and name not in REVERSAL_TOOLS,
                                 idempotent_hint=not write, open_world_hint=name in OPEN_WORLD_TOOLS)


async def list_tools(ctx, params):
    can_write = "wazuh:write" in _request_scopes(ctx)
    tools = [types.Tool(name=t["name"], description=t["description"], input_schema=t["inputSchema"], annotations=_annotations(t["name"]))
             for t in TOOL_DEFS if can_write or t["name"] not in WRITE_TOOLS]
    return types.ListToolsResult(tools=tools)


def _text(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)


async def call_tool(ctx, params):
    name = params.name
    args = dict(params.arguments or {})
    args.pop("cluster_id", None)
    args.pop("confirm", None)
    tool = TOOL_BY_NAME.get(name)
    if not tool:
        return _text(f"Error: Unknown tool '{name}'", True)
    if name in WRITE_TOOLS and "wazuh:write" not in _request_scopes(ctx):
        return _text(f"Error: Tool '{name}' requires the 'wazuh:write' scope. Mint a token from an API key with MOCK_API_KEY_SCOPES including wazuh:write.", True)
    unknown = set(args) - set(tool["inputSchema"].get("properties", {})) - ({"duration"} if name in ("wazuh_block_ip", "wazuh_firewall_drop") else set())
    if unknown:
        return _text(f"Error: Unknown argument(s) for {name}: {', '.join(sorted(unknown))}", True)
    for req in tool["inputSchema"].get("required", []):
        if args.get(req) in (None, ""):
            return _text(f"Error: Missing required argument '{req}' for {name}", True)
    try:
        result = await asyncio.to_thread(HANDLERS[name], ENV, args)
    except ToolError as e:
        return _text(f"Error: Invalid parameter — {e}", True)
    except Exception as e:  # pragma: no cover - defensive
        return _text(f"Error: {type(e).__name__}: {e}", True)
    return _text(f"{tool['label']}:\n{json.dumps(result, indent=2, default=str)}")


# ---------------------------------------------------------------------------
# MCP prompts (same five as the real server)
# ---------------------------------------------------------------------------
PROMPTS = [
    ("security_investigation", "Investigate a security incident using Wazuh data",
     [("incident_type", "Type of incident to investigate (e.g., malware, intrusion, data_breach)", True), ("time_range", "Time range for investigation (e.g., 1h, 24h, 7d)", False)],
     "Investigate a {incident_type} incident over the last {time_range}. Start with get_wazuh_alerts (level 10+), pivot on source IPs and agents with "
     "search_security_events, check affected hosts with get_agent_processes/get_agent_ports, enrich indicators with check_ioc_reputation, and summarise "
     "timeline, scope, MITRE techniques and recommended containment."),
    ("threat_hunt", "Perform proactive threat hunting across Wazuh agents",
     [("hunt_hypothesis", "The threat hypothesis to investigate", True), ("agent_scope", "Scope of agents to hunt (all, critical, specific)", False)],
     "Hunt for evidence of: {hunt_hypothesis} (scope: {agent_scope}). Baseline with get_alerts_aggregated, query with search_security_events, inspect "
     "processes/ports on candidate hosts, and report findings, confidence, and detection opportunities."),
    ("compliance_audit", "Generate compliance audit report for a specific framework",
     [("framework", "Compliance framework (PCI-DSS, HIPAA, SOX, GDPR, NIST)", True), ("include_remediation", "Include remediation recommendations", False)],
     "Run run_compliance_check for {framework}, review failed controls with supporting alerts, and produce an audit report (remediation: {include_remediation})."),
    ("vulnerability_assessment", "Assess vulnerabilities across the environment",
     [("severity_threshold", "Minimum severity to include (low, medium, high, critical)", False), ("agent_id", "Specific agent to assess (optional)", False)],
     "Assess vulnerabilities at or above {severity_threshold} (agent: {agent_id}) using get_wazuh_vulnerability_summary and get_wazuh_vulnerabilities; "
     "prioritise CISA KEV entries and internet-facing hosts."),
    ("iso27001_assessment", "Guided ISO 27001:2022 compliance assessment. Walks through dashboard overview, domain drill-down, gap analysis, and recommendations using live Wazuh data.",
     [("scope", "Assessment scope: 'full' (all domains), 'technological' (A.8 only), or 'specific_control' (single control)", False),
      ("control_id", "Specific control to assess when scope='specific_control' (e.g. 'A.8.8')", False), ("agent_id", "Scope assessment to a specific Wazuh agent (optional)", False)],
     "Perform an ISO 27001:2022 assessment (scope: {scope}, control: {control_id}, agent: {agent_id}) using get_iso27001_dashboard, "
     "get_iso27001_control_detail and get_iso27001_gap_analysis; finish with prioritised recommendations."),
]
PROMPT_BY_NAME = {p[0]: p for p in PROMPTS}


async def list_prompts(ctx, params):
    return types.ListPromptsResult(prompts=[types.Prompt(name=n, description=d, arguments=[types.PromptArgument(name=a, description=ad, required=r) for a, ad, r in args])
                                            for n, d, args, _ in PROMPTS])


async def get_prompt(ctx, params):
    p = PROMPT_BY_NAME.get(params.name)
    if not p:
        raise ValueError(f"Unknown prompt '{params.name}'")
    args = collections.defaultdict(lambda: "any", params.arguments or {})
    return types.GetPromptResult(description=p[1], messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=p[3].format_map(args)))])


server = Server("wazuh-mcp-server", version=VERSION, instructions="Mock Wazuh MCP Server (demo data)",
                on_list_tools=list_tools, on_call_tool=call_tool,
                on_list_prompts=list_prompts, on_get_prompt=get_prompt)


def build_app():
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=os.getenv("MOCK_STATELESS", "false") == "true",
        host="0.0.0.0",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        custom_starlette_routes=[Route("/auth/token", auth_token, methods=["POST"]), Route("/health", health, methods=["GET"])],
    )
    return RequireBearer(app)


def main():
    stop = threading.Event()
    threading.Thread(target=run_generator, args=(ENV, stop, float(os.getenv("MOCK_MIN_INTERVAL", "2")), float(os.getenv("MOCK_MAX_INTERVAL", "5"))),
                     daemon=True, name="alert-generator").start()
    print(f"[mock-wazuh] {len(TOOL_DEFS)} tools, {len(ENV.alerts)} backfilled alerts, auth={AUTH_MODE}", flush=True)
    uvicorn.run(build_app(), host=os.getenv("MOCK_HOST", "0.0.0.0"), port=int(os.getenv("MOCK_PORT", "3000")), log_level=os.getenv("MOCK_LOG_LEVEL", "warning"))
    stop.set()


if __name__ == "__main__":
    main()
