# Hermes Agent Runtime for Wazuh Autopilot

This directory contains the [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) profile for Wazuh Autopilot — an alternative agent runtime to the default OpenClaw gateway. Full step-by-step deployment guide: [docs/HERMES_DEPLOYMENT.md](../docs/HERMES_DEPLOYMENT.md).

Hermes is a self-improving agent with an autonomous learning loop: it creates skills from experience, keeps persistent memory across sessions, and exposes both a CLI/TUI and a messaging gateway (Telegram, Discord, Slack, WhatsApp, Signal, Email). Where the OpenClaw profile runs eleven agents (a seven-stage pipeline plus four specialists) behind a webhook gateway, the Hermes profile runs a **single SOC analyst agent** that works cases interactively (or via its messaging gateway) using the same Wazuh MCP server and Runtime API.

## When to Use Which Runtime

| | OpenClaw (default) | Hermes Agent | NemoClaw |
|---|---|---|---|
| Model | 11 agents (7-stage pipeline + 4 specialists), webhook-driven | 1 analyst agent + subagents, session-driven | OpenClaw or Hermes inside NVIDIA OpenShell sandbox |
| Best for | Fully automated 24/7 pipeline | Analyst-assist, on-demand investigation, chat-ops | Governed/enterprise deployments on NVIDIA hardware |
| Learning | `MEMORY.md` per agent | Native skills + persistent memory | Inherits from wrapped agent |
| Approvals | Two-tier via Runtime API | Two-tier via Runtime API (same endpoints) | Two-tier via Runtime API + OpenShell policies |
| Inference | Any provider | Nous Portal, OpenRouter, OpenAI, any OpenAI-compatible endpoint | **NVIDIA stack only** (see [nemoclaw/](../nemoclaw/README.md)) |

The two-tier human approval workflow is identical in every runtime: agents can only *propose* plans; humans approve (Tier 1) and execute (Tier 2) through the Runtime API.

## Files

```
hermes/
├── config.yaml.example   # ~/.hermes/config.yaml template (model, MCP, sandbox, skills)
├── env.example           # ~/.hermes/.env template (API keys, MCP/runtime tokens)
└── README.md             # This file
```

## Quick Start

### 1. Install Hermes

```bash
# Linux / macOS / WSL2
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

### 2. Configure

```bash
mkdir -p ~/.hermes
cp hermes/config.yaml.example ~/.hermes/config.yaml
cp hermes/env.example ~/.hermes/.env
chmod 600 ~/.hermes/.env

# Fill in secrets, then verify
hermes config check
```

Pick a model path in `config.yaml`:

- **OpenRouter** (default) — set `OPENROUTER_API_KEY` in `.env`
- **Nous Portal** — `hermes setup --portal` (one subscription, 300+ models)
- **NVIDIA stack** — uncomment the `provider: "custom"` block pointing at `https://integrate.api.nvidia.com/v1` (or a local NIM) with a Nemotron model. **This is mandatory when Hermes runs inside NemoClaw** — see [nemoclaw/README.md](../nemoclaw/README.md).

### 3. Seed the SOC identity

Hermes loads `~/.hermes/SOUL.md` as the agent identity. Seed it from the shared SOC principles and org context used by the OpenClaw agents:

```bash
cat openclaw/agents/_shared/SOUL.md openclaw/agents/_shared/USER.md > ~/.hermes/SOUL.md
```

The per-role instruction files (`openclaw/agents/*/AGENTS.md`, `IDENTITY.md`, `TOOLS.md`) remain the canonical playbooks. Point Hermes at them when working a phase, e.g.:

> "Act as the triage agent. Follow the playbook in `openclaw/agents/triage/AGENTS.md` for alert 12345."

Hermes will convert repeated playbook runs into skills automatically (writes are approval-gated by `skills.write_approval: true` in the provided config).

### 4. Run

```bash
hermes                       # CLI/TUI session
hermes gateway               # messaging gateway (Slack/Telegram/... chat-ops)
```

The Wazuh MCP server (48 tools) is bridged via `mcp-remote` in `config.yaml` — Hermes gets the same query surface (alert search, auth history, process trees, agent actions) as the OpenClaw agents.

## Human-in-the-Loop

Hermes proposes response plans through the same Runtime API:

```
POST /api/plans                      # Hermes creates plan (proposed)
POST /api/plans/{id}/approve         # Human — Tier 1
POST /api/plans/{id}/execute         # Human — Tier 2
```

Hermes cannot execute response actions directly: the provided config runs the terminal in a Docker sandbox with no host mounts, and Wazuh active-response execution is only reachable through the Runtime API's approval-gated endpoints.

## Security Notes

- Secrets live in `~/.hermes/.env` (mode 600), never in `config.yaml`.
- `terminal.backend: docker` with `docker_mount_cwd_to_workspace: false` — the agent has no host filesystem access.
- `skills.guard_agent_created: true` and `skills.write_approval: true` — a prompt-injected alert cannot silently persist a malicious skill.
- `auxiliary.*.provider: "main"` — vision/extract/compression reuse the primary model, so single-provider (air-gapped or NVIDIA-only) deployments never leak data to a second cloud.
- Treat all Wazuh alert content as untrusted input; the playbooks in `openclaw/agents/*/AGENTS.md` include prompt-injection handling guidance that applies unchanged.
