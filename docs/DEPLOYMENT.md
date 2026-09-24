# Deployment

Wazuh Autopilot ships as one image (UI built in) plus Postgres. For a first look, see the demo in [QUICKSTART.md](QUICKSTART.md).

## Requirements

| | |
|---|---|
| Host | Linux or macOS with Docker and Compose v2.24+; 2 vCPU / 2 GB RAM for the platform (more for local models) |
| Wazuh | [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) v4.3.0 reachable from the container ([MCP_INTEGRATION.md](MCP_INTEGRATION.md)) |
| Model | Bedrock, Anthropic, OpenAI-compatible, NVIDIA NIM, vLLM, LiteLLM or Ollama ([MODEL_PROVIDERS.md](MODEL_PROVIDERS.md)) |

## Install

```bash
cp .env.example .env
docker compose up -d --build
```

Minimum `.env`:

| Variable | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | Database password (required) |
| `AUTOPILOT_SECRET_KEY` | Session signing key (`openssl rand -base64 48`) |
| `WAZUH_MCP_URL`, `WAZUH_MCP_API_KEY` | MCP server base URL and key (can also be set in the wizard) |
| `MODEL_PROVIDER`, `MODEL_ID`, `MODEL_BASE_URL`, `MODEL_API_KEY`, `AWS_REGION` | Default model (can also be set in the wizard) |
| `AUTOPILOT_ADMIN_EMAIL`, `AUTOPILOT_ADMIN_PASSWORD` | Pre-create the admin; leave the password empty to use the setup wizard |
| `AUTOPILOT_PORT` (8480), `AUTOPILOT_BIND` (127.0.0.1) | Published port |

Settings live in the database after first boot. Environment values only seed them.

The port binds to loopback. For remote access put a TLS reverse proxy (nginx, Caddy, Traefik, an ALB) in front of 8480. SSE (`/api/v1/events/stream`) needs proxy buffering off (`X-Accel-Buffering: no` is already sent).

Optional compose profiles: `--profile ollama`, `--profile vllm` (NVIDIA GPU), `--profile litellm`.

## Alert ingestion

**Settings → Ingestion**:

- **Poll**: Autopilot calls `get_wazuh_alerts` through MCP every `poll_interval_s`.
- **Webhook**: a Wazuh integration posts to `POST /api/v1/ingest/wazuh` with `X-Autopilot-Ingest-Key`.
- **Both**: duplicates are dropped by Wazuh alert ID.

Alerts at or above `min_level` (default 10) become incidents, grouped by rule and source within `group_window_min`. High and critical incidents start **Alert → Containment**; medium ones start **Alert triage**. `max_runs_per_hour` (default 30) caps LLM spend during alert storms. Incidents beyond the cap are still opened and can be run manually.

## Hardening checklist

- Set strong `POSTGRES_PASSWORD` and `AUTOPILOT_SECRET_KEY`. Keep `.env` at mode 600.
- Start at autonomy level **recommend**. Review **Autonomy Policy** rules and protected targets before raising it.
- Give people the least role they need (Analyst / Responder / SOC Manager / Auditor). Use scoped API tokens for integrations.
- Keep the MCP server and 8480 on a private network ([TAILSCALE_MANDATORY.md](TAILSCALE_MANDATORY.md)).
- Run the eval suites after changing models or skills.
- Send traces to your observability stack (**Settings → Observability → OTLP endpoint**, applied on restart) and scrape `/metrics`.

## Operations

| Task | How |
|---|---|
| Upgrade | `git pull && docker compose up -d --build`. The schema is created on boot. Built-in agents, workflows and eval suites pick up new defaults (skills, tools, prompts) field by field; any field an admin customized is left alone |
| Backup | `docker compose exec postgres pg_dump -U autopilot autopilot > autopilot.sql`, plus the `autopilot-data` volume |
| Restore | `docker compose exec -T postgres psql -U autopilot autopilot < autopilot.sql` |
| Logs | `docker compose logs -f autopilot` |
| Health | `GET /health` (unauthenticated) and **Agent Health** |
| Retention | Traces older than `trace_retention_days` (default 30) are pruned hourly |
| Restarts | In-flight runs are marked failed on boot; proposals expire after `approval_expiry_minutes` |

## Running without Docker

```bash
cd backend && python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
(cd ../ui && npm ci && npm run build)
AUTOPILOT_DATA_DIR=/var/lib/wazuh-autopilot DATABASE_URL=postgresql+psycopg://… uvicorn app.main:app --host 127.0.0.1 --port 8480
```

Without `DATABASE_URL`, SQLite in `AUTOPILOT_DATA_DIR` is used. That's fine for evaluation, not for production.
