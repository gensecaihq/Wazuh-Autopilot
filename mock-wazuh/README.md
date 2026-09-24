# Mock Wazuh MCP Server

A demo stand-in for [gensecaihq/Wazuh-MCP-Server](https://github.com/gensecaihq/Wazuh-MCP-Server) v4.3.0. It exposes the same 55 tools (same names, descriptions and input schemas, copied from the real server), the same five MCP prompts, and the same auth flow. The data comes from a simulated Wazuh fleet instead of a real manager and indexer, so the platform can be demoed without a Wazuh deployment.

Don't point it at anything real. All indicators, reputations and compliance results are fictional.

## Endpoints

| Path | Behavior |
|---|---|
| `POST /mcp` | MCP Streamable HTTP. Requires `Authorization: Bearer <token>`, otherwise returns 401 |
| `POST /auth/token` | `{"api_key": "..."}` → `{"access_token", "token_type": "bearer", "expires_in", "scope"}` |
| `GET /health` | `{"status": "healthy", "version": "4.3.0-mock", ...}` |

Results use the real server's format: one text content block containing `"<Label>:\n<json>"`, for example `Wazuh Alerts:\n{"data": {"affected_items": [...], "total_affected_items": n}}`. Validation errors come back with `isError: true` and an `Error: ...` message.

As on the real server, write tools require the `wazuh:write` scope. With a read-only key they're hidden from `tools/list` (41 tools) and refused by `tools/call`.

## Simulated environment

- 14 agents: `wazuh-manager` (000), `web-prod-01/02`, `db-prod-01`, `dc-01` (Windows DC), `fin-ws-17` (Windows), `k8s-node-1..3`, `vpn-gw-01`, `mail-01`, `jump-01`, `dev-ws-04` (disconnected) and `backup-01`. Each has processes, ports, users and vulnerabilities (real CVE IDs, with CISA KEV entries flagged).
- Two planted compromises for agents to find:
  - an XMRig-style miner `kworkerd` (pid 31337) on `k8s-node-2`, connected to 45.155.205.233
  - a `rundll32` beacon (pid 6644, `msupdate.dll`) on `fin-ws-17`, calling back to 179.43.180.10
- At startup the server backfills 7 days of alerts (about 7.7k), then generates one every 2–5 seconds. Alerts use the full Wazuh JSON shape: `rule.mitre`, compliance tags, `GeoLocation`, `syscheck`, `data.win.*`.
- Recurring campaigns:

  | Campaign | Rules | MITRE |
  |---|---|---|
  | SSH brute force, sometimes ending in a login | 5710 / 5760 / 5712 / 5715 / 40111 | T1110, T1078 |
  | Web attacks on web-prod | 31103 / 31105 / 31104 / 31151 / 31106 | T1190, T1595 |
  | Windows logon failures and 4672 privilege use on dc-01 | 60122 / 60204 / 60106 / 67028 | — |
  | File integrity changes | 550 / 554 | — |
  | Miner activity | rootcheck 510, VirusTotal 87105 | — |
  | C2 beaconing | Sysmon | — |
  | Vulnerability detector | 23505 / 23506 | — |
- Active-response tools change state: blocked IPs, isolated hosts, killed processes, disabled users, quarantined files. They return the Wazuh dispatch-acceptance response and write an `active_response` alert. The `wazuh_check_*` tools report that state, and the rollback tools undo it. Every action is logged to stdout as `[mock-wazuh] ACTION ...`.

The fleet and backfill are seeded (`MOCK_SEED`), so every restart produces the same starting data.

## Run

```bash
docker build -t wazuh-mcp-mock mock-wazuh
docker run --rm -p 3000:3000 wazuh-mcp-mock

TOKEN=$(curl -s -X POST localhost:3000/auth/token -H 'content-type: application/json' \
  -d '{"api_key":"wazuh_demo_key"}' | jq -r .access_token)
```

Or run it without Docker: `pip install -r requirements.txt && python -m mock_wazuh`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MOCK_API_KEY` | `wazuh_demo_key` | API key accepted by `/auth/token`. It also works directly as a bearer token. |
| `MOCK_API_KEY_SCOPES` | `wazuh:read wazuh:write` | Scopes granted to minted tokens. Set to `wazuh:read` for a read-only key. |
| `MOCK_AUTH_MODE` | `bearer` | `none` disables auth (dev only) |
| `MOCK_AUTHLESS_ALLOW_WRITE` | `true` | Whether write tools are allowed when `MOCK_AUTH_MODE=none` |
| `MOCK_TOKEN_TTL` | `3600` | Token lifetime in seconds |
| `MOCK_SEED` | `1337` | Seed for the fleet and backfill |
| `MOCK_BACKFILL_DAYS` | `7` | Days of history to generate at startup |
| `MOCK_MAX_ALERTS` | `20000` | Size of the alert ring buffer |
| `MOCK_MIN_INTERVAL` / `MOCK_MAX_INTERVAL` | `2` / `5` | Seconds between live alerts |
| `MOCK_STATELESS` | `false` | Stateless Streamable HTTP mode |
| `MOCK_HOST` / `MOCK_PORT` | `0.0.0.0` / `3000` | Bind address and port |
| `MOCK_LOG_LEVEL` | `warning` | uvicorn log level |

## Differences from the real server

- There's no Wazuh API or indexer behind it. Queries run against the in-memory alert store.
- `check_ioc_reputation`, `analyze_security_threat` and `search_external_context` use built-in fictional intel. Nothing is sent off the box.
- The raw API key is also accepted as a bearer token (legacy-rest style). The real server requires the `/auth/token` exchange.
- There's no OAuth mode, multi-cluster routing (`list_wazuh_clusters` / `cluster_id`), `WAZUH_TOOLSETS` filtering, or `confirm` gate. `cluster_id` and `confirm` arguments are accepted and ignored.
- The check tools answer from simulated state instead of inferring from active-response alerts, so `isolation_confirmed` and `blocked` are exact.
