# NemoClaw Deployment (NVIDIA Stack) for Wazuh Autopilot

This directory contains the [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw) profile for Wazuh Autopilot. Full step-by-step deployment guide: [docs/NEMOCLAW_DEPLOYMENT.md](../docs/NEMOCLAW_DEPLOYMENT.md). NemoClaw is NVIDIA's enterprise distribution for running agents — OpenClaw, Hermes, LangChain Deep Agents — inside the **NVIDIA OpenShell** sandbox runtime with managed inference, network policies, snapshots, and lifecycle operations.

> **Rule: NemoClaw deployments run on the NVIDIA stack — end to end.**
>
> - **Models:** NVIDIA Nemotron 3 only (Ultra 550B / Super 120B / Nano 30B)
> - **Inference:** [build.nvidia.com](https://build.nvidia.com) hosted endpoints, local **NIM** microservices (TensorRT-LLM), or Ollama serving Nemotron models
> - **Runtime:** OpenShell sandbox — out-of-process policy enforcement (policies live *outside* the agent, so a compromised agent cannot bypass them)
> - **Hardware:** DGX Spark, DGX Station, RTX PRO workstations, GeForce RTX PCs, or WSL2 hosts (GPU optional when using hosted inference)
>
> No Anthropic/OpenAI/Google/etc. keys go into this profile. If you want mixed cloud providers, use the plain [OpenClaw profile](../openclaw/README.md) instead — NemoClaw's value is the governed, single-vendor path.

## Why NemoClaw for a SOC

If OpenClaw is the kernel, NemoClaw is the enterprise distribution. On top of the same seven Autopilot agents it adds:

| OpenShell feature | SOC benefit |
|---|---|
| Out-of-process policy enforcement | Prompt-injected alert content cannot disable the rules — they're enforced outside the agent process |
| Network policy tiers (deny-all default) | Agents can *only* reach the Wazuh MCP server, the Runtime API, and approved endpoints |
| Managed inference gateway (`inference.local` route) | Credentials never enter the agent container; provider rotation without config edits |
| Privacy Router | Sensitive queries can be pinned to local Nemotron (NIM/Ollama), bulk work to hosted endpoints |
| Snapshots & lifecycle ops | Roll a compromised or misbehaving sandbox back to a known-good state |

The two-tier human approval workflow is unchanged: agents propose plans; humans Approve (Tier 1) and Execute (Tier 2) via the Runtime API. OpenShell adds an *additional* enforcement layer around it.

## Files

```
nemoclaw/
├── openclaw-nemoclaw.json   # OpenClaw config pinned to the NVIDIA stack
└── README.md                # This file
```

## Prerequisites

- Ubuntu 22.04+, macOS (Apple Silicon), or Windows WSL2 · Node.js 20+ · Docker (or Colima/Docker Desktop)
- 8 GB RAM / 20 GB disk minimum (16 GB / 40 GB recommended)
- GPU optional — required only for local Nemotron inference (8 GB+ VRAM; 24 GB+ for Nano 30B via NIM)
- An NVIDIA API key from [build.nvidia.com](https://build.nvidia.com) (`nvapi-...`) for hosted inference

## Quick Start

### 1. Install NemoClaw and create the sandbox

Interactive (wizard picks agent, provider, model, policies):

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
nemoclaw onboard
```

Non-interactive (recommended for repeatable installs):

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 \
  NEMOCLAW_AGENT=openclaw \
  NEMOCLAW_PROVIDER=build \
  NVIDIA_INFERENCE_API_KEY=nvapi-... \
  NEMOCLAW_SANDBOX_NAME=wazuh-autopilot \
  bash
```

Select **OpenClaw** as the agent. NemoClaw registers the provider with the OpenShell gateway and sets the `inference.local` route — credentials stay outside the container.

### 2. Choose a network policy tier

NemoClaw prompts for a policy tier after sandbox creation. For a SOC deployment choose **Restricted**, then allowlist only what the pipeline needs:

| Endpoint | Why |
|---|---|
| `MCP_URL` (Tailscale IP:3000) | Wazuh MCP server — 48 query/response tools |
| `AUTOPILOT_RUNTIME_URL` | Case/plan API, two-tier approvals |
| `integrate.api.nvidia.com` | Hosted Nemotron inference (omit if fully local) |
| Slack endpoints (optional) | Approval channel, if used |

Leave PyPI/npm/GitHub egress (from the Balanced preset) **off** — the SOC agents never install packages at runtime.

### 3. Apply the Autopilot configuration

NemoClaw requires a fresh OpenClaw install inside the sandbox, so apply the config after creation:

```bash
nemoclaw wazuh-autopilot connect

# Inside the sandbox:
cp nemoclaw/openclaw-nemoclaw.json ~/.openclaw/openclaw.json
mkdir -p ~/.openclaw/wazuh-autopilot
cp -r openclaw/agents ~/.openclaw/wazuh-autopilot/

openclaw models scan     # REQUIRED — registers tool-calling capability for the
                         # openai-completions providers; skipping this makes all
                         # agents emit tool calls as plain text and silently stall
openclaw doctor --fix
```

### 4. Verify

```bash
nemoclaw wazuh-autopilot status    # sandbox, provider, model, inference.local, GPU
nemoclaw launch wazuh-autopilot    # dashboard on 127.0.0.1:18789 (authenticated)

# Smoke-test an agent inside the sandbox:
openclaw agent --agent wazuh-triage --local -m "status check" --session-id smoke
```

## Inference Options (all NVIDIA)

| Path | Model refs in `openclaw-nemoclaw.json` | Hardware | Notes |
|---|---|---|---|
| **Hosted — build.nvidia.com** | `nvidia/nvidia/nemotron-3-super-120b-a12b` (default), `...ultra-550b-a55b`, `...nano-30b-a3b` | None (CPU host OK) | OpenAI-compatible at `integrate.api.nvidia.com/v1`; 1M-token context on Super/Ultra |
| **Local NIM microservice** | `nim-local/nvidia/nemotron-3-nano-30b-a3b` | 24 GB+ VRAM GPU | TensorRT-LLM optimized container from `nvcr.io/nim/...`; fully offline; verify served id via `curl http://127.0.0.1:8000/v1/models` |
| **Ollama (experimental)** | via `NEMOCLAW_PROVIDER=ollama NEMOCLAW_MODEL=nemotron-3-nano:30b` | 24 GB+ VRAM GPU | `ollama pull nemotron-3-nano:30b` first; Ollama must be running before the installer |

Model role assignments in the config: **Super 120B** for triage/correlation/planning/response (best agentic tool calling per cost), **Ultra 550B** for deep investigation, **Nano 30B** for heartbeats and reporting. Memory-search embeddings run locally (GGUF) so nothing leaves the NVIDIA path.

For a fully air-gapped DGX/RTX deployment, set the default `model.primary` to `nim-local/nvidia/nemotron-3-nano-30b-a3b`, remove the hosted `nvidia` provider block, and keep the OpenShell tier on Restricted with no internet egress. See also [docs/AIR_GAPPED_DEPLOYMENT.md](../docs/AIR_GAPPED_DEPLOYMENT.md).

## Related NVIDIA Ecosystem

- **[Nemotron](https://developer.nvidia.com/nemotron)** — open model family powering all inference in this profile
- **[NIM](https://developer.nvidia.com/nim)** — inference microservices (TensorRT-LLM) for self-hosting Nemotron
- **[NeMo](https://developer.nvidia.com/nemo)** — fine-tune/specialize Nemotron on your SOC's alert corpus (e.g., a triage-tuned Nano)
- **NeMo Guardrails / NeMo Agent Toolkit** — optional programmable rails and agent profiling on top of the pipeline
- **OpenShell** — the sandbox runtime NemoClaw is built on
- **Hermes under NemoClaw** — `nemohermes onboard` runs the [Hermes profile](../hermes/README.md) inside OpenShell; the same NVIDIA-stack rule applies (use the NVIDIA `custom` endpoint block in `hermes/config.yaml.example`)

## Troubleshooting

| Symptom | Fix |
|---|---|
| Agents output tool calls as plain text, cases never advance | You skipped `openclaw models scan` inside the sandbox |
| `404` from inference | Model id mismatch — check `curl .../v1/models` against the `id` fields in the config |
| Webhooks from the runtime service never arrive | Runtime URL not in the OpenShell network policy allowlist |
| `NEMOCLAW_*` installer exits in CI | Add `NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 NEMOCLAW_NON_INTERACTIVE=1` |
| Ollama provider not detected | Start Ollama before the installer; on WSL2 set `OLLAMA_HOST=0.0.0.0` |
