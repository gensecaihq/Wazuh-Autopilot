# Hermes Agent Deployment Guide

Run Wazuh Autopilot on the [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) — a self-improving agent runtime with an autonomous learning loop, persistent memory, and a multi-platform messaging gateway. This guide covers a full deployment; the profile files live in [`hermes/`](../hermes/).

**When to choose Hermes over OpenClaw**: you want an analyst-assist / chat-ops model (one expert agent you converse with, which spawns subagents for parallel work) rather than the fully automated 7-agent webhook pipeline. Both use the same Wazuh MCP server, Runtime API, and two-tier human approval workflow.

## Quick Start

### 1. Install Hermes

```bash
# Linux / macOS / WSL2
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Windows (native): PowerShell installer bundles uv, Python 3.11, Node.js,
# ripgrep, ffmpeg, and a portable Git — see hermes-agent.nousresearch.com/docs
```

### 2. Apply the Autopilot Profile

```bash
mkdir -p ~/.hermes
cp hermes/config.yaml.example ~/.hermes/config.yaml
cp hermes/env.example ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

Configuration precedence (highest first): CLI arguments → `~/.hermes/config.yaml` → `~/.hermes/.env` → built-in defaults. **Secrets go in `.env`; everything else goes in `config.yaml`** — `hermes config set KEY value` routes each to the right file automatically.

### 3. Choose a Model Provider

```bash
hermes model                 # interactive picker
# or directly:
hermes config set model anthropic/claude-sonnet-4-5
```

| Path | Setup | Notes |
|---|---|---|
| **OpenRouter** (default in the profile) | `OPENROUTER_API_KEY` in `.env` | Single key, 300+ models, no subscription-token ban risk |
| **Nous Portal** | `hermes setup --portal` | OAuth; one subscription covering 300+ models |
| **Any OpenAI-compatible endpoint** | `provider: "custom"` + `base_url` in `config.yaml` | vLLM, NIM, Ollama, LM Studio, etc. |
| **NVIDIA stack** | `base_url: https://integrate.api.nvidia.com/v1` + `NVIDIA_API_KEY`, Nemotron model | **Mandatory when running under NemoClaw** — see [NEMOCLAW_DEPLOYMENT.md](NEMOCLAW_DEPLOYMENT.md) |

The profile pins `auxiliary.vision/web_extract/compression` to `provider: "main"` so single-provider deployments (air-gapped, NVIDIA-only) never silently call a second cloud.

### 4. Seed the SOC Identity

Hermes loads `~/.hermes/SOUL.md` as its identity. Seed it from the shared SOC principles (which include the [team roster and personas](../openclaw/agents/_shared/SOUL.md)) plus your organizational context:

```bash
cat openclaw/agents/_shared/SOUL.md openclaw/agents/_shared/USER.md > ~/.hermes/SOUL.md
```

### 5. Verify and Run

```bash
hermes config check          # validate configuration
hermes                       # CLI/TUI session
hermes gateway               # messaging gateway (Slack, Telegram, Discord, ...)
```

## Wazuh Integration

### MCP Server (55 tools)

The Wazuh MCP server is HTTP-based; the profile bridges it to Hermes' stdio MCP client with `mcp-remote`:

```yaml
mcp_servers:
  wazuh:
    command: "npx"
    args:
      - "-y"
      - "mcp-remote"
      - "${MCP_URL}"
      - "--header"
      - "Authorization: Bearer ${AUTOPILOT_MCP_AUTH}"
```

`${VAR}` references resolve from `~/.hermes/.env`. Set `MCP_URL` and `AUTOPILOT_MCP_AUTH` there.

### Runtime API (cases, plans, approvals)

Hermes reaches the Runtime Service at `AUTOPILOT_RUNTIME_URL` for the same case/plan lifecycle as the OpenClaw agents:

```
POST /api/plans                   # Hermes proposes (state: proposed)
POST /api/plans/{id}/approve      # Human — Tier 1
POST /api/plans/{id}/execute      # Human — Tier 2
```

Hermes cannot execute active-response directly: execution only happens through the Runtime API's approval-gated endpoints, and the terminal sandbox (below) has no host access.

## Idle Cost & Shared Runtime Behavior

Two notes on how issues seen in the OpenClaw runtime map to Hermes:

- **Heartbeat idle cost does not apply.** Hermes has no timer-based heartbeat: it is inherently event/session-driven (CLI/TUI or the messaging gateway responds to input), so it runs **zero idle inference** when there are no alerts — the node returns to baseline on its own. This is the event-driven behavior that the OpenClaw runtime now offers via `heartbeat: "0m"` (see [HEARTBEATS_AND_COST.md](HEARTBEATS_AND_COST.md)); with Hermes you get it by default. If you wire an external poller to feed alerts into Hermes, size its interval deliberately — that poller, not Hermes, becomes the idle-cost knob.
- **Runtime-level fixes apply automatically.** Case/plan state lives in the shared Runtime Service, not in the agent runtime. So the fixes for *new alerts grouped into terminal cases* and *plan-expiry persistence* (issue #33) are already in effect for Hermes — they are enforced by the Runtime API that Hermes calls, identical to OpenClaw and NemoClaw.

## Working Cases

Point Hermes at the canonical per-role playbooks when working a pipeline phase:

> "Act as the Tier 1 triage analyst. Follow `openclaw/agents/triage/AGENTS.md` for alert 12345."

For parallel workstreams (e.g., one pivot per host during an investigation), Hermes spawns isolated subagents. Repeated playbook runs become Hermes **skills** automatically — the profile gates skill writes behind approval (`skills.write_approval: true`) so a prompt-injected alert cannot persist a malicious skill.

## Security Configuration

| Setting (in the profile) | Why |
|---|---|
| `terminal.backend: docker`, `docker_mount_cwd_to_workspace: false` | Agent shell runs in a container with no host filesystem access |
| `docker_forward_env` limited to `MCP_URL`, `AUTOPILOT_MCP_AUTH`, `AUTOPILOT_RUNTIME_URL` | No stray secrets enter the sandbox |
| `skills.guard_agent_created: true` + `skills.write_approval: true` | Skill writes are scanned and human-approved |
| `memory.write_approval: false`, memory enabled | FP patterns / attack signatures accumulate (Hermes-native equivalent of `MEMORY.md`) |
| `.env` mode 600 | Secrets never in `config.yaml` |

Alternative terminal backends (`ssh`, `modal`, `daytona`, `vercel_sandbox`, `singularity`) are supported by Hermes; keep the no-host-mount principle whichever you choose.

## Useful Commands

```bash
hermes setup                 # full setup wizard
hermes model                 # switch LLM provider/model
hermes tools                 # enable/disable toolsets
hermes config get/set KEY    # individual settings
hermes config check          # verify after edits
hermes config migrate        # add newly introduced options after upgrades
/reasoning high --global     # runtime reasoning-effort change (in-session)
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| MCP tools missing in session | Check `npx -y mcp-remote $MCP_URL` runs standalone; verify `AUTOPILOT_MCP_AUTH` and that `${VAR}` names in `config.yaml` match `.env` |
| Provider auth errors | `hermes config check`; confirm the key is in `.env` (not `config.yaml`) and the provider name matches (`openrouter`, `custom`, ...) |
| Long investigations truncate context | Compression is enabled at 50% threshold in the profile; lower `compression.threshold` or raise `protect_last_n` |
| Wazuh query output truncated | Raise `tool_output.max_bytes` / `max_lines` (profile defaults: 50 000 / 2 000) |
| Skill write blocked unexpectedly | That's the approval gate (`skills.write_approval: true`) — approve interactively or disable only in trusted dev environments |
