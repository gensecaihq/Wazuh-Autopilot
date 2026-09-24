# Troubleshooting

Start with **Agent Health** (component status: database, Wazuh MCP, model, scheduler, ingestion) and **Runs & Traces** (every span with its error). Container logs: `docker compose logs -f autopilot`.

## Platform

| Symptom | Fix |
|---|---|
| Browser shows a different app on 8480 | Another process holds the port. Set `AUTOPILOT_PORT` in `.env`. |
| `docker compose up` fails with `!reset` | Compose is older than v2.24. Upgrade Docker Compose. |
| Postgres "superuser password is not specified" | Set `POSTGRES_PASSWORD` in `.env` (the demo overlay sets one). |
| Logged out after every restart | Set `AUTOPILOT_SECRET_KEY`, or keep the `autopilot-data` volume (a generated key is stored there). |
| Setup wizard doesn't appear | `AUTOPILOT_ADMIN_PASSWORD` was set, so an admin already exists. Sign in with `AUTOPILOT_ADMIN_EMAIL`. |
| Runs marked "Interrupted by platform restart" | Expected. Runs in flight during a restart are failed on boot; replay them from Runs. |

## Wazuh MCP

| Symptom | Fix |
|---|---|
| Wazuh MCP "down" | Check the base URL has no `/mcp` suffix and is reachable from the container (`docker compose exec autopilot python -c "import urllib.request;print(urllib.request.urlopen('<url>/health').read())"`). |
| Test shows "read-only key" | Set `MCP_API_KEY_SCOPES="wazuh:read wazuh:write"` on the MCP server and use a new key. |
| Actions fail with a scope or permission error | Same as above. |
| Action executed but not verified | Wazuh accepted the command but the check tool didn't confirm it. Look at the action's verification note and the Responder's finding. The agent may be disconnected, or the active-response script missing. |
| No new alerts | **Settings → Ingestion**: mode must include poll (or configure the webhook), and `min_level` may be too high. Health shows the last poll and any error. |

## Agents and models

| Symptom | Fix |
|---|---|
| Model test fails | Check provider, model ID and credentials. For Bedrock, enable model access in the region and check IAM. |
| Agents answer without calling tools | The model doesn't do tool calling well. Use a stronger model, or for vLLM enable `--enable-auto-tool-choice` with the right parser. |
| Ollama agents lose instructions or print raw JSON | Context window too small. Keep "Context window" at ≥ 32768. |
| Proposals refused | The run trace shows the policy reason: observe mode, protected target, or a disabled action type. |
| Incidents opened but no runs | The hourly run budget (`max_runs_per_hour`) was reached. |
| Swarm stops early | Max handoffs, iterations or timeouts reached (**Settings → Swarm limits**). |
| `ImportError` from `strands` in a custom build | You installed `strands` instead of `strands-agents`. |

