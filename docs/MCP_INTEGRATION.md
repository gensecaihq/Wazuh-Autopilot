# Wazuh MCP Server Integration

Autopilot reaches Wazuh only through [gensecaihq/Wazuh-MCP-Server](https://github.com/gensecaihq/Wazuh-MCP-Server) v4.3.0, over MCP Streamable HTTP at `<base>/mcp`.

## Connect

1. Deploy the MCP server next to your Wazuh manager (see its README). For active response, give the key write scope:
   ```bash
   MCP_API_KEY_SCOPES="wazuh:read wazuh:write"
   ```
2. In Autopilot, **Settings → Wazuh MCP**: set the base URL (without `/mcp`) and the API key, then **Test connection**. The test reports the tool count, how many write tools are exposed, and whether the token carries `wazuh:write`.

Authentication: Autopilot exchanges the API key for a JWT at `POST <base>/auth/token`, caches it for 50 minutes, refreshes on 401, and falls back to sending the raw key if the server has no token endpoint.

With a read-only key, agents still investigate and propose, but execution fails with a scope error. That's a reasonable first week.

## How the tools are used

| Who | Tools | Why |
|---|---|---|
| Agents | 36 query tools + 5 `wazuh_check_*` tools, per agent allowlist (the server's `security_investigation`, `threat_hunt`, `compliance_audit` and `vulnerability_assessment` are MCP prompts, not tools, so agents don't use them) | Investigation and verification |
| Platform executor | 9 action tools + 5 rollback tools | Approved response actions only |
| Ingestion poller | `get_wazuh_alerts` | Pull mode (Settings → Ingestion) |

The agents' MCP client drops every state-changing tool (`^wazuh_(?!check_)`) when it lists tools, and a pre-tool hook blocks any that slip through. Both are covered by tests (`backend/tests/test_policy_catalog.py`, `test_roster_skills.py`).

Toolsets on the MCP server (`WAZUH_TOOLSETS`) still apply. Hiding `response` there disables execution, and hiding `web_search` keeps indicators from going to the external search provider.

## Alerts in

| Mode | Setup |
|---|---|
| Poll | Autopilot calls `get_wazuh_alerts` every `poll_interval_s` from a moving cursor. Nothing to install on the manager. |
| Webhook | A Wazuh integration posts alerts to `POST /api/v1/ingest/wazuh` with header `X-Autopilot-Ingest-Key` (**Settings → Ingestion** shows the key). Accepts one alert, a list, or `{"alerts": [...]}`. |
| Both | Duplicates are dropped by Wazuh alert ID. |

## Mock server

`mock-wazuh/` implements the same 55 tool names and input schemas, the same result format and the same auth flow against a simulated fleet. The demo overlay uses it, and it's handy for testing agent changes without touching production Wazuh. Don't point it at anything real.
