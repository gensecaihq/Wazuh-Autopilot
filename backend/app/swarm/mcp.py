"""Wazuh MCP Server connectivity (gensecaihq/Wazuh-MCP-Server v4.3.0).

Two clients:
  * the agents' client drops every state-changing wazuh_* tool at list time, so
    no model ever sees an active-response tool;
  * the executor's client is unfiltered and is used only by the platform after
    policy evaluation and approval.
"""

import base64
import json
import logging
import re
import threading
import time
import uuid
from datetime import timedelta

import httpx
from strands.tools.mcp import MCPClient

log = logging.getLogger(__name__)

# Active-response and rollback tools. wazuh_check_* are read-only verification tools.
ACTION_TOOL_PATTERN = r"^wazuh_(?!check_)"
_ACTION_RE = re.compile(ACTION_TOOL_PATTERN)


def is_action_tool(name: str) -> bool:
    return bool(_ACTION_RE.match(name))


class WazuhMcpAuth(httpx.Auth):
    """Exchanges the MCP API key for a JWT at POST /auth/token; refreshes on 401.

    Falls back to sending the raw key when the server has no token endpoint.
    """

    JWT_TTL_SECONDS = 50 * 60

    def __init__(self, base_url: str, api_key: str, verify: bool = True):
        self._base_url = base_url
        self._api_key = api_key
        self._verify = verify
        self._jwt: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def token(self, refresh: bool = False) -> str:
        with self._lock:
            if not refresh and self._jwt and time.time() < self._expires_at:
                return self._jwt
            try:
                resp = httpx.post(f"{self._base_url}/auth/token", json={"api_key": self._api_key},
                                  timeout=10, verify=self._verify)
                data = resp.json() if resp.is_success else {}
            except (httpx.HTTPError, ValueError):
                data = {}
            tok = data.get("access_token") or data.get("token")
            if not tok:
                return self._api_key
            self._jwt, self._expires_at = tok, time.time() + self.JWT_TTL_SECONDS
            return tok

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.token()}"
        response = yield request
        if response.status_code == 401:
            request.headers["Authorization"] = f"Bearer {self.token(refresh=True)}"
            yield request


def _jwt_scopes(token: str) -> list[str] | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    raw = claims.get("scope") or claims.get("scopes") or claims.get("scp")
    if raw is None:
        return None
    return raw.split() if isinstance(raw, str) else list(raw)


def result_text(result: dict) -> str:
    parts = []
    for block in result.get("content", []) or []:
        if isinstance(block, dict) and "text" in block:
            parts.append(block["text"])
        elif isinstance(block, dict) and "json" in block:
            parts.append(json.dumps(block["json"]))
    return "\n".join(parts)


class WazuhMCP:
    """Lazily connected, auto-reconnecting MCP clients keyed by settings."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._key: tuple | None = None
        self._agent_client: MCPClient | None = None
        self._agent_tools: list = []
        self._exec_client: MCPClient | None = None
        self._auth: WazuhMcpAuth | None = None
        self.last_error: str | None = None

    @staticmethod
    def _base(settings: dict) -> str:
        url = (settings.get("mcp_url") or "").rstrip("/")
        return url[:-4] if url.endswith("/mcp") else url

    def configured(self, settings: dict) -> bool:
        return bool(self._base(settings))

    def _make_client(self, settings: dict, filtered: bool) -> MCPClient:
        base = self._base(settings)
        kwargs = {}
        if settings.get("api_key"):
            kwargs["auth_provider"] = self._auth
        if filtered:
            kwargs["tool_filters"] = {"rejected": [_ACTION_RE]}
        return MCPClient(url=f"{base}/mcp", application_name="wazuh-autopilot",
                         startup_timeout=int(settings.get("request_timeout_s") or 30), **kwargs)

    def _ensure(self, settings: dict) -> None:
        key = (self._base(settings), settings.get("api_key"), settings.get("verify_tls", True))
        if key == self._key and self._agent_client is not None:
            return
        self.close()
        self._auth = WazuhMcpAuth(self._base(settings), settings.get("api_key") or "",
                                  verify=settings.get("verify_tls", True))
        client = self._make_client(settings, filtered=True)
        client.start()
        tools = client.list_tools_sync()
        self._agent_client, self._agent_tools, self._key = client, list(tools), key
        self.last_error = None

    def agent_tools(self, settings: dict) -> list:
        """Read-only MCP tools (action tools removed). Empty list when unavailable."""
        if not self.configured(settings):
            return []
        with self._lock:
            try:
                self._ensure(settings)
                return list(self._agent_tools)
            except Exception as e:  # MCP down must not take the swarm down
                self.last_error = f"{type(e).__name__}: {e}"
                log.warning("Wazuh MCP unavailable: %s", self.last_error)
                self.close()
                return []

    def execute(self, settings: dict, tool: str, arguments: dict, timeout_s: int = 60) -> dict:
        """Call any MCP tool (including action tools). Platform executor only."""
        with self._lock:
            self._ensure(settings)
            if self._exec_client is None:
                self._exec_client = self._make_client(settings, filtered=False)
                self._exec_client.start()
            client = self._exec_client
        result = client.call_tool_sync(f"exec-{uuid.uuid4().hex[:8]}", tool, arguments,
                                       read_timeout_seconds=timedelta(seconds=timeout_s))
        return dict(result)

    def test(self, settings: dict) -> dict:
        started = time.time()
        if not self.configured(settings):
            return {"ok": False, "error": "MCP URL is not set", "latency_ms": 0}
        base = self._base(settings)
        client = None
        try:
            auth = WazuhMcpAuth(base, settings.get("api_key") or "", verify=settings.get("verify_tls", True))
            token = auth.token() if settings.get("api_key") else ""
            scopes = _jwt_scopes(token) if token else None
            version = None
            try:
                h = httpx.get(f"{base}/health", timeout=5, verify=settings.get("verify_tls", True)).json()
                version = h.get("version")
            except Exception:
                pass
            client = MCPClient(url=f"{base}/mcp", auth_provider=auth if settings.get("api_key") else None,
                               startup_timeout=15)
            client.start()
            names = [t.tool_name for t in client.list_tools_sync()]
            write = [n for n in names if is_action_tool(n)]
            return {
                "ok": True, "latency_ms": int((time.time() - started) * 1000), "tools_total": len(names),
                "tools_read": len(names) - len(write), "tools_write": len(write),
                "write_scope": (scopes is not None and "wazuh:write" in scopes) if scopes is not None else None,
                "version": version,
            }
        except Exception as e:
            return {"ok": False, "latency_ms": int((time.time() - started) * 1000), "error": f"{type(e).__name__}: {e}"}
        finally:
            if client is not None:
                try:
                    client.stop(None, None, None)
                except Exception:
                    pass

    def close(self) -> None:
        for c in (self._agent_client, self._exec_client):
            if c is not None:
                try:
                    c.stop(None, None, None)
                except Exception:
                    pass
        self._agent_client = self._exec_client = None
        self._agent_tools = []
        self._key = None


wazuh = WazuhMCP()
