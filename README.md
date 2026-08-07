<div align="center">

<h1>🛡️ Wazuh Autopilot</h1>

<h3>Your Wazuh SIEM, run by an autonomous AI SOC team — that triages, investigates, and responds in seconds, while humans stay in control.</h3>

<p>
  <strong>Seven security-expert AI agents work every alert like a real SOC shift — Tier 1 → Tier 2 → DFIR → IR Lead → Compliance → Containment → SOC Manager.</strong><br/>
  Every containment action is gated behind two-tier human approval. No alert goes unread. Every decision leaves an evidence trail.
</p>

<p>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/releases"><img src="https://img.shields.io/github/v/release/gensecaihq/Wazuh-Autopilot?color=2ea44f&label=release&style=flat-square" alt="Release"/></a>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"/></a>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/actions"><img src="https://img.shields.io/github/actions/workflow/status/gensecaihq/Wazuh-Autopilot/ci.yml?label=CI&style=flat-square" alt="CI"/></a>
  <img src="https://img.shields.io/badge/tests-582%20passing-2ea44f?style=flat-square" alt="Tests"/>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/issues"><img src="https://img.shields.io/github/issues/gensecaihq/Wazuh-Autopilot?style=flat-square" alt="Issues"/></a>
  <a href="https://github.com/gensecaihq/Wazuh-Autopilot/stargazers"><img src="https://img.shields.io/github/stars/gensecaihq/Wazuh-Autopilot?style=social" alt="Stars"/></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Wazuh-0080FF?style=for-the-badge&logo=wazuh&logoColor=white" alt="Wazuh"/>
  <img src="https://img.shields.io/badge/OpenClaw-FF6B35?style=for-the-badge&logoColor=white" alt="OpenClaw"/>
  <img src="https://img.shields.io/badge/Hermes-6E56CF?style=for-the-badge&logoColor=white" alt="Hermes Agent"/>
  <img src="https://img.shields.io/badge/NVIDIA%20NemoClaw-76B900?style=for-the-badge&logo=nvidia&logoColor=white" alt="NVIDIA NemoClaw"/>
  <img src="https://img.shields.io/badge/MCP-6B4FBB?style=for-the-badge&logoColor=white" alt="MCP"/>
</p>

<p>
  <a href="#-quick-start"><b>Quick Start</b></a> &nbsp;·&nbsp;
  <a href="#-how-it-works"><b>How It Works</b></a> &nbsp;·&nbsp;
  <a href="#-agent-runtimes"><b>Runtimes</b></a> &nbsp;·&nbsp;
  <a href="#-deployment-options"><b>Deploy</b></a> &nbsp;·&nbsp;
  <a href="docs/RUNTIME_API.md"><b>API</b></a> &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md"><b>Architecture</b></a> &nbsp;·&nbsp;
  <a href="CHANGELOG.md"><b>Changelog</b></a>
</p>

</div>

---

> **Wazuh Autopilot** closes the gap between *detection* and *response*. A Wazuh alert that used to wait hours in a queue is triaged in ~40 seconds, correlated across your fleet, investigated with 7+ live pivot queries, and turned into a risk-assessed response plan — all before an analyst opens their laptop. When it's time to act, a human clicks **Approve** and **Execute**. Nothing dangerous happens without you.

<div align="center">

**⚡ ~40s triage** &nbsp;·&nbsp; **🔍 7+ auto pivots/case** &nbsp;·&nbsp; **✅ 2-tier human approval** &nbsp;·&nbsp; **🧩 48 Wazuh MCP tools** &nbsp;·&nbsp; **🕓 24/7 coverage** &nbsp;·&nbsp; **🔒 air-gap ready**

</div>

---

## ⭐ Why Star This Project

- **A real SOC team, not a chatbot** — seven agents with distinct security-expert personas and strict handoffs, mirroring a human 24/7 shift.
- **Humans stay in control** — AI *proposes*, humans *approve* and *execute*. Two-tier approval with separation of duties, enforced in code.
- **Runs anywhere** — cloud LLMs, self-hosted GPU (vLLM), fully air-gapped (Ollama), or the NVIDIA stack (NemoClaw + Nemotron) — same pipeline.
- **Three agent runtimes** — [OpenClaw](openclaw/README.md) (default), [Hermes](docs/HERMES_DEPLOYMENT.md) (analyst chat-ops), [NemoClaw](docs/NEMOCLAW_DEPLOYMENT.md) (governed, NVIDIA-sandboxed).
- **Production-grade** — 582 passing tests, structured evidence packs, Prometheus SOC KPIs, policy engine, crash recovery, security-audited.

---

## What It Does

A Wazuh alert fires. Within minutes — not hours — your SOC has:

1. **Triaged** the alert with entity extraction, MITRE mapping, and severity assessment
2. **Correlated** it with related alerts across hosts, IPs, and users
3. **Investigated** via live Wazuh queries — auth history, process trees, lateral movement checks
4. **Generated a response plan** with risk assessment and rollback procedures
5. **Executed the response** (IP block, host isolation, process kill) — only after human approval

No alert sits unread. No playbook gets skipped. Every action has an evidence trail.

### Before and After

| | Without Autopilot | With Autopilot |
|---|---|---|
| **Alert triage** | Manual review, 15-60 min per alert | Automatic, ~40 seconds |
| **Investigation** | Analyst runs queries, cross-references | 7+ pivot queries run automatically |
| **Response** | Find playbook, execute manually | Risk-assessed plan, one-click approve |
| **Evidence** | Scattered across tools | Structured JSON evidence pack per case |
| **Coverage** | Business hours, analyst availability | 24/7, every alert processed |

---

## 🔬 How It Works

```
  Wazuh Alert
       │
       ▼
  ┌─────────┐    ┌─────────────┐    ┌───────────────┐    ┌──────────────┐
  │ Triage  │───▶│ Correlation │───▶│ Investigation │───▶│   Response   │
  │  Agent  │    │    Agent    │    │    Agent      │    │   Planner    │
  └─────────┘    └─────────────┘    └───────────────┘    └──────┬───────┘
   Extract IOCs   Group related      Query Wazuh via       Generate plan
   Map MITRE       alerts into        MCP (48 tools)       Assess risk
   Set severity    unified cases      Build timeline       Assign actions
                                                                │
                                                                ▼
                                                     ┌──────────────────┐
                                                     │  Policy Guard    │
                                                     │  + Human Review  │
                                                     └────────┬─────────┘
                                                              │
                                                     [Approve] [Reject]
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │   Responder      │
                                                     │   (Execution)    │
                                                     └──────────────────┘
                                                      block_ip, isolate_host,
                                                      kill_process, disable_user...
```

**7 specialized agents** work as a pipeline. Each agent has a single responsibility, its own playbook, and communicates through the runtime service via webhooks. The runtime enforces policy at every step — action allowlists, confidence thresholds, rate limits, time windows, and idempotency checks.

**AI agents never act autonomously.** Every response action requires explicit two-tier human approval (Approve + Execute). The responder capability is disabled by default.

---

## Key Features

**Detection & Analysis**
- Autonomous alert triage with entity extraction (IPs, users, hosts, hashes)
- MITRE ATT&CK technique and tactic mapping
- Entity-based alert grouping into unified cases
- AbuseIPDB IP reputation enrichment with TTL caching
- Investigation agent runs 7+ pivot queries per case via [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) (48 tools)

**Response & Enforcement**
- Risk-assessed response plans with rollback metadata
- 9 Wazuh Active Response actions (block IP, isolate host, kill process, disable user, quarantine file, firewall drop, host deny, restart, generic AR)
- Inline policy enforcement: action allowlists, confidence thresholds, approver authorization, evidence requirements, time windows, rate limits, idempotency
- Two-tier approval workflow with separation of duties

**Observability & Reporting**
- Structured JSON evidence packs for compliance and forensics
- Prometheus metrics with SOC KPIs (MTTD, MTTT, MTTI, MTTR, MTTC)
- KPI endpoint with SLA compliance tracking
- Reporting agent generates hourly, daily, weekly, and monthly SOC health reports
- Slack integration with real-time alerts and interactive approval buttons (Socket Mode)

**Operations**
- Crash recovery for plans stuck mid-execution
- Stalled pipeline detection with automatic re-dispatch
- Alert dedup across date boundaries
- LLM type coercion for local model compatibility
- Investigation findings auto-promoted to case severity/confidence

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Description |
|---|---|
| [Wazuh](https://wazuh.com) 4.8+ | SIEM platform, installed and running |
| [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) v4.2.1+ | MCP bridge for Wazuh API (48 tools) |
| [OpenClaw](https://github.com/openclaw/openclaw) v2026.7.1+ | AI agent framework (latest stable; tested with v2026.7.1-2 — `npm install -g openclaw@latest`) |
| Node.js 20+ | Runtime service (22+ recommended) |
| LLM API Key | Claude, GPT, Groq, Mistral, or [local Ollama/vLLM](#local-llm-options) |

### Install

```bash
git clone https://github.com/gensecaihq/Wazuh-Autopilot.git
cd Wazuh-Autopilot
sudo ./install/install.sh
```

The installer handles MCP Server setup, OpenClaw configuration, agent deployment, and optional Slack integration. For air-gapped environments, use `--mode bootstrap`.

### Configure

```bash
sudo nano /etc/wazuh-autopilot/.env
```

```bash
# Wazuh connection
WAZUH_HOST=localhost
WAZUH_PORT=55000
WAZUH_USER=wazuh-wui
WAZUH_PASS=your-password

# LLM provider (pick one — we recommend OpenRouter for simplicity)
OPENROUTER_API_KEY=sk-or-...

# Optional: Slack approval buttons
SLACK_APP_TOKEN=xapp-...
SLACK_BOT_TOKEN=xoxb-...
```

### Verify

```bash
curl http://localhost:9090/health
curl http://localhost:9090/metrics
```

---

## 📦 Deployment Options

| Method | Best For | Command |
|---|---|---|
| **Docker Compose** | Production | `docker-compose up -d` |
| **Systemd** | Native Linux | `sudo ./install/install.sh` |
| **Air-gapped** | Classified / offline | `sudo ./install/install.sh --mode bootstrap` + [guide](docs/AIR_GAPPED_DEPLOYMENT.md) |
| **vLLM** | Self-hosted GPU | [vLLM Guide](docs/VLLM_DEPLOYMENT.md) |
| **NemoClaw (NVIDIA)** | Governed / enterprise, NVIDIA stack | `curl -fsSL https://www.nvidia.com/nemoclaw.sh \| bash` + [guide](docs/NEMOCLAW_DEPLOYMENT.md) |
| **Hermes Agent** | Analyst-assist / chat-ops | `curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` + [guide](docs/HERMES_DEPLOYMENT.md) |
| **Manual** | Development | `cd runtime/autopilot-service && npm start` |

---

## 🤖 Agent Runtimes

The Autopilot pipeline runs on your choice of agent runtime:

| Runtime | Shape | Inference | Guide |
|---|---|---|---|
| **[OpenClaw](openclaw/README.md)** (default) | 7 pipeline agents, webhook-driven, 24/7 | Any provider | [openclaw/](openclaw/README.md) |
| **[Hermes Agent](hermes/README.md)** (Nous Research) | Single self-improving SOC analyst + subagents; CLI/TUI and messaging gateway | Nous Portal, OpenRouter, any OpenAI-compatible endpoint | [HERMES_DEPLOYMENT.md](docs/HERMES_DEPLOYMENT.md) |
| **[NemoClaw](nemoclaw/README.md)** (NVIDIA) | OpenClaw or Hermes wrapped in the NVIDIA OpenShell sandbox — policy enforcement outside the agent, managed inference, snapshots | **NVIDIA stack only**: Nemotron 3 via build.nvidia.com, local NIM, or Ollama-Nemotron | [NEMOCLAW_DEPLOYMENT.md](docs/NEMOCLAW_DEPLOYMENT.md) |

> **NemoClaw rule**: a NemoClaw deployment is NVIDIA end-to-end — Nemotron 3 models, NIM/build.nvidia.com inference, OpenShell runtime. No third-party model providers. See [nemoclaw/README.md](nemoclaw/README.md).

All runtimes share the same Wazuh MCP server, Runtime API, and two-tier human approval workflow.

### Scaling to a Swarm

The seven agents form a virtual SOC team (see [agent personas](openclaw/agents/_shared/SOUL.md)) — and the same roles scale horizontally into a swarm when alert volume demands it:

- **OpenClaw**: raise `agents.defaults.maxConcurrent` and per-agent heartbeat frequency — each webhook delivery and heartbeat run is an independent session, so one triage agent definition fans out across many alerts in parallel.
- **Hermes**: the analyst agent spawns isolated **subagents** for parallel workstreams (e.g., one per pivot during a multi-host investigation).
- **NemoClaw**: run multiple OpenShell sandboxes (`NEMOCLAW_SANDBOX_NAME=wazuh-autopilot-{1..n}`) behind the same Runtime API for fleet-style isolation — each sandbox is independently policed, snapshotted, and rollback-able.

Whatever the swarm size, every response action still funnels through the single Policy Guard gate and two-tier human approval — more workers, same chain of command.

---

## LLM Providers

OpenClaw is model-agnostic. Use any provider:

| Provider | Best For | Cost |
|---|---|---|
| [OpenRouter](https://openrouter.ai/) | Safest option — 300+ models, single key, no ban risk | Pay per token |
| [Anthropic](https://console.anthropic.com/) | Best reasoning (Claude) | Pay per token |
| [Groq](https://console.groq.com/) | Ultra-fast inference | Free tier available |
| [Ollama](https://ollama.com) | Air-gapped / free | Free (local) |
| [vLLM](https://github.com/vllm-project/vllm) | Self-hosted GPU inference | Hardware only |
| [NVIDIA build.nvidia.com](https://build.nvidia.com) | Nemotron 3 hosted / NIM local — required for [NemoClaw](nemoclaw/README.md) | Free tier available |

Plus OpenAI, Google, Mistral, xAI, Together, Cerebras. See [full provider guide](#provider-details) below.

> **API Keys Only**: Use pay-per-token API keys, not subscription OAuth tokens. Anthropic and Google have banned subscription tokens in third-party tools. [Details](#provider-policy-notice).

---

## Human-in-the-Loop Approval

```
 PROPOSED ────▶ APPROVED ────▶ EXECUTED
    │               │               │
    ▼               ▼               ▼
 Policy Check   Policy Check    Policy Check
 ─ allowlist    ─ approver ID   ─ evidence
 ─ confidence   ─ risk level    ─ time window
 ─ time window                  ─ rate limit
                                ─ idempotency
```

AI agents generate plans. Humans approve them. The runtime enforces policy at every step. **No action executes without human authorization.**

---

## Wazuh Compatibility

Tested via [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) v4.2.1 (48 tools):

| Wazuh Version | Status |
|---|---|
| **4.14.x** | Fully Supported (recommended) |
| 4.8.x – 4.13.x | Fully Supported |
| 4.0.0 – 4.7.x | Limited (no vulnerability tools) |

Platforms: Ubuntu 22.04/24.04, Debian 11/12, RHEL/Rocky/AlmaLinux 8/9, Docker.

---

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `POST /api/alerts` | POST | Ingest Wazuh alert — triggers full pipeline |
| `GET /api/cases` | GET | List cases (filter: `?status=`, `?severity=`, `?since=`, `?until=`) |
| `GET /api/cases/summary` | GET | Aggregated case statistics |
| `GET /api/cases/:id` | GET | Full case with evidence pack |
| `GET /api/plans` | GET | List plans (filter: `?state=`, `?case_id=`) |
| `GET /api/plans/:id` | GET | Plan details |
| `POST /api/plans/:id/approve` | POST | Approve plan (Tier 1) |
| `POST /api/plans/:id/execute` | POST | Execute plan (Tier 2) |
| `GET /api/kpis` | GET | SLA/KPI metrics (`?period=24h`) |
| `GET /api/reports` | GET | List stored reports |
| `GET /metrics` | GET | Prometheus metrics |

### Agent Action Endpoints (GET-based for `web_fetch`)

| Endpoint | Description |
|---|---|
| `/api/agent-action/update-case` | Update case status/data |
| `/api/agent-action/create-plan` | Create response plan |
| `/api/agent-action/approve-plan` | Approve/deny plan |
| `/api/agent-action/execute-plan` | Execute approved plan |
| `/api/agent-action/store-report` | Store generated report |
| `/api/agent-action/search-alerts` | Proxy search to Wazuh MCP |

Full API documentation: [RUNTIME_API.md](docs/RUNTIME_API.md)

---

## SOC KPIs & Reporting

The runtime tracks case status transitions and computes SLA metrics:

```bash
curl http://localhost:9090/api/kpis?period=24h
```

```json
{
  "period": "24h",
  "cases_analyzed": 50,
  "mttt": 42,
  "mtti": 138,
  "mttr": 280,
  "mttc": 450,
  "auto_triage_rate": 0.92,
  "false_positive_rate": 0.18,
  "sla_compliance": {
    "triage_within_15m": 0.95,
    "response_within_1h": 0.82
  }
}
```

The reporting agent generates hourly, daily, weekly, and monthly SOC health reports automatically.

---

## Evidence Packs

Every case produces a structured evidence pack for compliance and forensics:

```json
{
  "case_id": "CASE-20260327-1df903b68bc7",
  "severity": "high",
  "confidence": 0.95,
  "entities": [
    {"type": "ip", "value": "176.120.22.47", "role": "source"},
    {"type": "host", "value": "virt-5378", "role": "victim"}
  ],
  "mitre": [{"technique_id": "T1110.001", "tactic": "Credential Access"}],
  "investigation_notes": "200+ failed SSH login attempts over 7 days...",
  "findings": {"classification": "brute_force", "confidence": 0.95},
  "status_history": [
    {"from": "open", "to": "triaged", "timestamp": "..."},
    {"from": "triaged", "to": "investigated", "timestamp": "..."}
  ],
  "plans": [...],
  "actions": [...],
  "mcp_calls": [...]
}
```

---

## Security

| Layer | Protection |
|---|---|
| **Network** | All services localhost-only. Tailscale zero-trust for inter-node. |
| **Auth** | Bearer token + query param auth. Timing-safe comparison. |
| **Policy** | Inline enforcement at every pipeline step. Fail-closed in production. |
| **Agents** | Sandboxed execution. Anti-injection instructions. No `exec` access. |
| **Approval** | Two-tier human approval. Separation of duties. Bootstrap gate requires explicit opt-in. |
| **MCP** | RBAC scopes (`wazuh:read`/`wazuh:write`). JWT auth. Circuit breaker. |

---

## Slack Integration

Socket Mode — outbound-only, no webhooks or public endpoints required:

- Real-time alert notifications with severity coloring
- Interactive **[Approve]** / **[Reject]** / **[Execute]** buttons
- Slash commands: `/wazuh status`, `/wazuh approve`, `/wazuh execute`
- Confirmation dialogs for destructive actions

---

## Project Structure

```
├── install/install.sh              # Security-hardened installer
├── docker-compose.yml              # Production container orchestration
├── openclaw/
│   ├── openclaw.json               # Gateway & model config
│   └── agents/                     # 7 SOC agents (AGENTS.md, TOOLS.md, IDENTITY.md)
├── hermes/                         # Hermes Agent runtime profile (Nous Research)
├── nemoclaw/                       # NemoClaw profile — NVIDIA stack only (Nemotron/NIM/OpenShell)
├── runtime/autopilot-service/
│   ├── index.js                    # Runtime service (6,900+ LOC)
│   ├── slack.js                    # Slack Socket Mode integration
│   └── *.test.js                   # 582 tests across 16 files
├── policies/
│   ├── policy.yaml                 # Action allowlists, approvers, thresholds
│   └── toolmap.yaml                # MCP tool mappings (9 action tools)
├── playbooks/                      # 7 incident response playbooks
└── docs/                           # 19 documentation files
```

---

## Local LLM Options

### Ollama (Air-Gapped)

Zero external network calls. Full data sovereignty. See [Air-Gapped Guide](docs/AIR_GAPPED_DEPLOYMENT.md).

```bash
sudo ./install/install.sh --mode bootstrap
```

### vLLM (Self-Hosted GPU)

Production-grade throughput with open-source models. See [vLLM Guide](docs/VLLM_DEPLOYMENT.md).

```bash
vllm serve Qwen/Qwen3-32B --enable-auto-tool-choice --tool-call-parser hermes
```

| Model | VRAM | Best For |
|---|---|---|
| Qwen3 32B | ~64 GB | Best tool calling |
| Llama 3.3 70B | ~140 GB | Strongest reasoning |
| DeepSeek-R1 70B | ~140 GB | Chain-of-thought |

---

## Provider Details

<details>
<summary>Full provider list and configuration</summary>

| Provider | Models | API Key Env |
|---|---|---|
| [OpenRouter](https://openrouter.ai/) | 300+ models | `OPENROUTER_API_KEY` |
| [Anthropic](https://console.anthropic.com/) | Claude Sonnet 4.5, Haiku 4.5 | `ANTHROPIC_API_KEY` |
| [OpenAI](https://platform.openai.com/) | GPT-4o, o3-mini | `OPENAI_API_KEY` |
| [Groq](https://console.groq.com/) | Llama 3.3 70B, Mixtral | `GROQ_API_KEY` |
| [Google](https://aistudio.google.com/) | Gemini 2.0 Flash/Pro | `GOOGLE_API_KEY` |
| [Mistral](https://console.mistral.ai/) | Mistral Large, Codestral | `MISTRAL_API_KEY` |
| [xAI](https://console.x.ai/) | Grok 2, Grok 3 | `XAI_API_KEY` |
| [Ollama](https://ollama.com) | Llama, Mistral, Qwen | N/A (local) |
| [vLLM](https://github.com/vllm-project/vllm) | Any HuggingFace model | `VLLM_API_KEY` |
| [Together](https://together.xyz/) | Open-source models | `TOGETHER_API_KEY` |
| [Cerebras](https://cerebras.ai/) | Ultra-fast inference | `CEREBRAS_API_KEY` |

Model format: `"provider/model-name"` (e.g., `"anthropic/claude-sonnet-4-5"`).

### Cost Optimization

| Task | Recommended Model | Why |
|---|---|---|
| Complex investigation | `anthropic/claude-sonnet-4-5` | Best reasoning |
| High-volume triage | `groq/llama-3.3-70b-versatile` | Fast and free |
| Heartbeats | `anthropic/claude-haiku-4-5` | Cheapest Claude |
| Air-gapped | `ollama/llama3.3` | No network |
| GPU self-hosted | `vllm/qwen3-32b` | Best open-source tool calling |

</details>

---

## Provider Policy Notice

<details>
<summary>Important: API keys vs subscription tokens</summary>

Anthropic and Google have **banned** subscription-plan OAuth tokens (Claude Pro/Max, Google AI Ultra) in third-party tools. Using them will result in account suspension.

**Always use pay-per-token API keys** from the provider's developer console, or route through **OpenRouter** (billing proxy, no ban risk).

- **OpenRouter**: Single key, 300+ models, no restrictions
- **Groq, Mistral, xAI, Together, Cerebras**: No restrictions reported

</details>

---

## Documentation

**Start here**

| Document | Description |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture — pipeline, runtimes, MCP, control plane |
| [QUICKSTART.md](docs/QUICKSTART.md) | Installation guide (under 15 minutes) |
| [SCENARIOS.md](docs/SCENARIOS.md) | End-to-end attack scenarios you can replay |

**Operate**

| Document | Description |
|---|---|
| [RUNTIME_API.md](docs/RUNTIME_API.md) | REST API reference |
| [CLI_REFERENCE.md](docs/CLI_REFERENCE.md) | Command-line reference |
| [POLICY_AND_APPROVALS.md](docs/POLICY_AND_APPROVALS.md) | Policy engine and approval workflow |
| [SLACK_SOCKET_MODE.md](docs/SLACK_SOCKET_MODE.md) | Slack setup |
| [OBSERVABILITY_EXPORT.md](docs/OBSERVABILITY_EXPORT.md) | Prometheus metrics and SOC KPIs |
| [HEARTBEATS_AND_COST.md](docs/HEARTBEATS_AND_COST.md) | Heartbeat inference cost and event-driven tuning |
| [EVIDENCE_PACK_SCHEMA.md](docs/EVIDENCE_PACK_SCHEMA.md) | Evidence pack format |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and fixes |

**Deploy & integrate**

| Document | Description |
|---|---|
| [AGENT_CONFIGURATION.md](docs/AGENT_CONFIGURATION.md) | Agent files, personas, and customization |
| [AGENT_COMMUNICATION.md](docs/AGENT_COMMUNICATION.md) | Agent-to-runtime message flow |
| [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) | MCP server integration (48 tools) |
| [TAILSCALE_MANDATORY.md](docs/TAILSCALE_MANDATORY.md) | Mandatory Tailscale network isolation |
| [AIR_GAPPED_DEPLOYMENT.md](docs/AIR_GAPPED_DEPLOYMENT.md) | Offline deployment with Ollama |
| [VLLM_DEPLOYMENT.md](docs/VLLM_DEPLOYMENT.md) | Self-hosted GPU inference with vLLM |
| [HERMES_DEPLOYMENT.md](docs/HERMES_DEPLOYMENT.md) | Hermes Agent runtime (Nous Research) |
| [NEMOCLAW_DEPLOYMENT.md](docs/NEMOCLAW_DEPLOYMENT.md) | NemoClaw on the NVIDIA stack (OpenShell, Nemotron, NIM) |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## Contributing

```bash
cd runtime/autopilot-service
npm install
npm test   # 582 tests across 16 files, all passing
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Acknowledgments

Huge thanks to [**@idrone3d**](https://github.com/idrone3d) for exceptionally thorough field testing of Wazuh Autopilot on real, self-hosted local hardware, and for the detailed findings and suggestions in [issue #33](https://github.com/gensecaihq/Wazuh-Autopilot/issues/33). That work directly drove several improvements, including:

- **Heartbeat operational cost** — surfacing that timer-based heartbeats dominate idle inference on small local models and paid APIs, which led to relaxed defaults and the new [event-driven tuning guide](docs/HEARTBEATS_AND_COST.md).
- **New alerts grouped into terminal cases** — a correctness bug where a fresh alert could be merged into an already-closed/executed case.
- **Plan-expiry persistence** — expired plans that reverted to actionable after a restart.

Community testing like this makes the project meaningfully better. Thank you. 🙏

---

## Community

- [GitHub Discussions](https://github.com/gensecaihq/Wazuh-Autopilot/discussions) — Questions, ideas, deployment help
- [GitHub Issues](https://github.com/gensecaihq/Wazuh-Autopilot/issues) — Bug reports and feature requests

---

## Related Projects

| Project | Description |
|---|---|
| [Wazuh MCP Server](https://github.com/gensecaihq/Wazuh-MCP-Server) | MCP bridge for Wazuh API (48 tools, RBAC, audit logging) |
| [OpenClaw](https://github.com/openclaw/openclaw) | AI agent framework powering the SOC agents |

---

## License

MIT License — see [LICENSE](LICENSE)

---

<p align="center">
  <sub>Built by <a href="https://github.com/gensecaihq">GenSecAI</a></sub>
</p>
