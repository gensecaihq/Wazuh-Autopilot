# Quick Start

## Demo (5 minutes, no Wazuh or LLM needed)

```bash
git clone https://github.com/gensecaihq/Wazuh-Autopilot.git && cd Wazuh-Autopilot
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
```

Open <http://localhost:8480> and sign in as `admin@autopilot.local` / `Autopilot!2026`. Other demo users (same password): `maya.chen@autopilot.local` (SOC Manager), `sam.okafor@autopilot.local` (Responder), `lena.ivanova@autopilot.local` (Analyst), `raj.patel@autopilot.local` (Auditor).

What's running:

- **autopilot**: the platform (API, UI, swarm) on port 8480.
- **postgres**: platform database.
- **mock-wazuh**: a simulated Wazuh MCP Server with 14 agents, a live alert stream, and two planted compromises (a miner on `k8s-node-2`, a beacon on `fin-ws-17`).

The demo uses the scripted `demo` model. Each agent follows a fixed procedure but makes real tool calls, so cases, findings, action proposals, execution and verification all happen for real. Things to try:

1. **Command Center**: live detections and swarm activity.
2. **Incidents**: open a new one and read the timeline, findings and ATT&CK mapping the agents produced.
3. **Approvals**: approve a proposed `block_ip`. The platform executes it on the mock fleet and verifies it with `wazuh_check_blocked_ip`.
4. **Runs & Traces**: the waterfall of every agent, model call, tool call and handoff.
5. **Playground**: chat with one agent in dry-run mode and watch its tool calls stream.
6. **Settings → Models**: switch to a real provider (Bedrock, Anthropic, OpenAI-compatible, NVIDIA NIM, vLLM, LiteLLM, Ollama) to see real reasoning against the same fleet.

Stop it with `docker compose -f docker-compose.yml -f docker-compose.demo.yml down` (add `-v` to wipe data).

## First production install

Prerequisites: Docker with Compose v2.24+, a [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) v4.3.0 reachable from the host, and a model provider.

```bash
cp .env.example .env
# set POSTGRES_PASSWORD, AUTOPILOT_SECRET_KEY, WAZUH_MCP_URL, WAZUH_MCP_API_KEY, MODEL_PROVIDER/MODEL_ID
docker compose up -d --build
```

Leave `AUTOPILOT_ADMIN_PASSWORD` empty and the first visit opens the setup wizard: organization → administrator → Wazuh MCP (with connection test) → model (with test) → autonomy level → review.

Start with the autonomy level at **recommend** (humans approve and execute everything), watch a few days of proposals, then relax specific action types in **Autonomy Policy**. For active response, the MCP key needs `wazuh:write` scope. See [MCP_INTEGRATION.md](MCP_INTEGRATION.md).

Next: [DEPLOYMENT.md](DEPLOYMENT.md) for ingestion, TLS, backups and operations.
