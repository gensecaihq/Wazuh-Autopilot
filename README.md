<div align="center">

<h1>🛡️ Wazuh Autopilot</h1>

<h3>An agentic SOC for Wazuh, built on Strands Agents. A 13-agent swarm triages, investigates and responds through the Wazuh MCP Server, and humans stay in control.</h3>

<p>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/releases"><img src="https://img.shields.io/github/v/release/gensecaihq/Wazuh-Autopilot?color=2ea44f&label=release&style=flat-square" alt="Release"/></a>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"/></a>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/actions"><img src="https://img.shields.io/github/actions/workflow/status/gensecaihq/Wazuh-Autopilot/ci.yml?label=CI&style=flat-square" alt="CI"/></a>
  <img src="https://img.shields.io/badge/tests-41%20passing-2ea44f?style=flat-square" alt="Tests"/>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/stargazers"><img src="https://img.shields.io/github/stars/gensecaihq/Wazuh-Autopilot?style=social" alt="Stars"/></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Wazuh-0080FF?style=for-the-badge&logo=wazuh&logoColor=white" alt="Wazuh"/>
  <img src="https://img.shields.io/badge/Strands%20Agents-FF8127?style=for-the-badge&logoColor=white" alt="Strands Agents"/>
  <img src="https://img.shields.io/badge/MCP-6B4FBB?style=for-the-badge&logoColor=white" alt="MCP"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
</p>

<p>
  <a href="#quick-start"><b>Quick Start</b></a> &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md"><b>Architecture</b></a> &nbsp;·&nbsp;
  <a href="docs/DEPLOYMENT.md"><b>Deploy</b></a> &nbsp;·&nbsp;
  <a href="docs/AGENTS_AND_SKILLS.md"><b>Agents & Skills</b></a> &nbsp;·&nbsp;
  <a href="docs/API.md"><b>API</b></a> &nbsp;·&nbsp;
  <a href="CHANGELOG.md"><b>Changelog</b></a>
</p>

</div>

---

Wazuh Autopilot is a self-hosted platform that works your Wazuh alerts with a swarm of [Strands](https://strandsagents.com) agents. They reach Wazuh only through the [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) (v4.3.0, 55 tools). Alerts become incidents. Agents triage, correlate, investigate, enrich and plan the response, and every containment step goes through an autonomy policy you control, from "observe only" to "fully autonomous for low-risk actions". Everything runs in one container plus Postgres and ships with a web console.

**⚡ Minutes, not hours** &nbsp;·&nbsp; **🤖 13 agents / 37 skills** &nbsp;·&nbsp; **🧭 NIST · MITRE · CIS · ISO · PCI** &nbsp;·&nbsp; **✅ Policy-gated response** &nbsp;·&nbsp; **🔭 Full tracing** &nbsp;·&nbsp; **🔒 Air-gap ready**

## Quick start

```bash
git clone https://github.com/gensecaihq/Wazuh-Autopilot.git && cd Wazuh-Autopilot
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
open http://localhost:8480     # admin@autopilot.local / Autopilot!2026
```

The demo runs against a simulated Wazuh fleet (`mock-wazuh/`: same tools and schemas as the real MCP server, live alerts, two planted compromises) and a scripted demo model, so it needs neither Wazuh nor an LLM key. Tool calls, policy decisions, approvals, execution and verification are all real. To see real reasoning, pick a model in **Settings → Models**.

For production, `cp .env.example .env`, point it at your Wazuh MCP Server and model provider, and run `docker compose up -d`. The first visit opens the setup wizard. See [docs/QUICKSTART.md](docs/QUICKSTART.md) and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## What you get

| | |
|---|---|
| **Agent swarm** | SOC Commander, Tier 1–3 analysts, CTI analyst, threat hunter, vulnerability manager, IR lead, SecOps engineer, detection engineer, GRC analyst, Wazuh platform engineer and SOC manager. Workflows run as a Strands `Swarm` (agents hand off to each other) or a `Graph` (fixed pipeline). |
| **Skills** | 37 [Agent Skills](https://agentskills.io) (`SKILL.md`): 9 Wazuh-specific skills (MCP querying, rules and decoders, FIM, SCA, malware, Windows/Sysmon, cloud and containers, active response, platform health), 7 incident-response playbooks (brute force, lateral movement, privilege escalation, ransomware, suspicious PowerShell, data exfiltration, vulnerability spike). Agents load them on demand. |
| **Standards** | NIST CSF 2.0, SP 800-61r3, SP 800-53r5, MITRE ATT&CK and D3FEND, CIS v8.1, ISO/IEC 27001:2022, PCI DSS v4.0.1, SANS PICERL, CISA KEV / FIRST EPSS / SSVC, Sigma, OWASP LLM Top 10. |
| **Autonomy policy** | Four levels: observe, recommend, supervised, autonomous. Plus per-action rules (confidence floor, hourly budget), per-agent caps, protected targets, a two-person rule and a business-hours limit. Critical actions always need a human. |
| **Safe by construction** | Agents never receive state-changing Wazuh tools: the MCP tool filter and a pre-tool hook both block them. The platform runs approved actions, verifies them with `wazuh_check_*`, and can roll them back. |
| **Console** | Command center, alerts, incidents, approvals, agent roster, swarm topology, skills, workflows, agent playground/debugger, evals, run traces, metrics, agent health, policy, standards coverage, audit log, settings, users/roles/API tokens, setup wizard. |
| **Models** | Amazon Bedrock (with Guardrails), Anthropic, OpenAI-compatible, NVIDIA NIM (Nemotron), vLLM, LiteLLM, Ollama. Swarm-wide default with per-agent overrides. |
| **Operations** | RBAC (5 roles), audit log, Postgres, OpenTelemetry export, Prometheus `/metrics`, `strands-agents-evals` suites, restart recovery, trace retention. |

## How it works

```
Wazuh ──► Wazuh MCP Server ◄──────────────── agents (read + verify tools only)
              ▲      │ alerts (poll or webhook)
              │      ▼
              │   Autopilot ── incidents ──► Strands swarm: triage → correlation → investigation → CTI → IR lead
              │      │                                                   │ propose_action
              │      ▼                                                   ▼
              └── executor ◄── approved ◄── autonomy policy ── approvals queue (humans)
                     └── verify (wazuh_check_*) · audit · rollback
```

Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository layout

```
backend/        FastAPI + Strands swarm, policy engine, executor (Python 3.12)
  app/skills/   37 SKILL.md skills
  tests/        pytest suite
ui/             React + TypeScript console
mock-wazuh/     simulated Wazuh MCP server for demos and tests
litellm/        LiteLLM proxy config (compose profile)
docs/           documentation
```

## Documentation

| | |
|---|---|
| [QUICKSTART.md](docs/QUICKSTART.md) | Demo and first production install |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment, ingestion, operations |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flow, security boundaries |
| [AGENTS_AND_SKILLS.md](docs/AGENTS_AND_SKILLS.md) | Roster, skills, workflows, standards |
| [AUTONOMY_AND_APPROVALS.md](docs/AUTONOMY_AND_APPROVALS.md) | Autonomy levels, action rules, approvals, execution and verification |
| [MODEL_PROVIDERS.md](docs/MODEL_PROVIDERS.md) | Bedrock, Anthropic, OpenAI-compatible, NVIDIA NIM, vLLM, LiteLLM, Ollama, air-gapped |
| [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) | Connecting the Wazuh MCP Server |
| [TAILSCALE_MANDATORY.md](docs/TAILSCALE_MANDATORY.md) | Network isolation |
| [API.md](docs/API.md) | REST API (OpenAPI at `/api/docs`) |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common problems |

## Development

```bash
cd backend && python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt && pytest -q
cd ../ui && npm ci && npm run build
```

See [CONTRIBUTING.md](CONTRIBUTING.md). The PyPI package is `strands-agents`: `pip install strands` installs an unrelated library, and `strands-evals` isn't the official evals package (`strands-agents-evals` is).

## Acknowledgments

Thanks to [**@idrone3d**](https://github.com/idrone3d) for thorough field testing on self-hosted hardware and the findings in [issue #33](https://github.com/gensecaihq/Wazuh-Autopilot/issues/33): idle inference cost from timer-driven agents, new alerts being grouped into closed cases, and proposals surviving expiry across restarts. The platform has no heartbeat polling: agents run on incidents, and the scheduled workflows (hunts, sweeps, briefings, platform-health checks; about a dozen runs a day by default) can be disabled or rescheduled in Workflows. It groups alerts only into open incidents and stores proposal expiry in the database.

## Related projects

| Project | Description |
|---|---|
| [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) | MCP bridge for the Wazuh API (55 tools, RBAC, audit logging) |
| [Strands Agents](https://strandsagents.com) | Open-source agent SDK the swarm is built on |

## License

MIT, see [LICENSE](LICENSE).
