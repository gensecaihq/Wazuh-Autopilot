# NemoClaw Deployment Guide (NVIDIA Stack)

Run Wazuh Autopilot inside [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw) — NVIDIA's reference stack for running agents (OpenClaw, Hermes, LangChain Deep Agents) safely inside **NVIDIA OpenShell** sandboxes with managed inference, network policies, snapshots, and lifecycle operations. The profile files live in [`nemoclaw/`](../nemoclaw/).

> **Project rule — NVIDIA end to end.** A NemoClaw deployment uses **only** the NVIDIA stack: Nemotron 3 models, inference via build.nvidia.com / local NIM / Ollama-Nemotron, OpenShell runtime. No third-party model providers or keys. This is enforced by CI (`openclaw-config.test.js` → "NemoClaw profile is NVIDIA-stack only"). For mixed cloud providers use the plain [OpenClaw profile](../openclaw/README.md) instead.

## Why OpenShell for a SOC

OpenShell enforces policy **out of process**: rules live outside the agent, so even a fully prompt-injected agent cannot bypass them. On top of the Autopilot's own controls (Policy Guard, two-tier approvals) it adds deny-all-by-default network egress, credential isolation (keys never enter the agent container — the gateway holds them and exposes an `inference.local` route), and sandbox snapshots/rollback.

## Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04+, macOS (Apple Silicon), or Windows WSL2 | — |
| Node.js | v20+ | v22 |
| Container runtime | Docker, Colima, or Docker Desktop | — |
| RAM / Disk | 8 GB / 20 GB free | 16 GB / 40 GB |
| GPU | None (hosted inference) | 8 GB+ VRAM for local Nemotron; 24 GB+ for Nano 30B via NIM |
| API key | [build.nvidia.com](https://build.nvidia.com) key (`nvapi-...`) for hosted inference | — |

Supported hardware targets: DGX Spark, DGX Station, RTX PRO workstations, GeForce RTX PCs, WSL2 hosts.

## Install

### Quick install (recommended)

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
nemoclaw onboard        # interactive wizard: agent, provider, model, policies
```

Select **OpenClaw** as the agent when prompted.

### Non-interactive (CI / repeatable)

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 \
  NEMOCLAW_NON_INTERACTIVE=1 \
  NEMOCLAW_AGENT=openclaw \
  NEMOCLAW_PROVIDER=build \
  NVIDIA_INFERENCE_API_KEY=nvapi-... \
  NEMOCLAW_SANDBOX_NAME=wazuh-autopilot \
  bash
```

### npm / source alternatives

```bash
npm install -g git+https://github.com/NVIDIA/NemoClaw.git && nemoclaw onboard
# or
git clone https://github.com/NVIDIA/NemoClaw.git && cd NemoClaw && sudo npm install -g . && nemoclaw onboard
```

NemoClaw state lives in `~/.nemoclaw/` (config: `~/.nemoclaw/config.yaml`); sandbox definitions live in the OpenShell registry.

## Inference Options (all NVIDIA)

| Path | Env / selection | Model refs in the profile | Hardware |
|---|---|---|---|
| **Hosted — build.nvidia.com** | `NEMOCLAW_PROVIDER=build`, `NVIDIA_INFERENCE_API_KEY` | `nvidia/nvidia/nemotron-3-super-120b-a12b` (default), `nvidia/nvidia/nemotron-3-ultra-550b-a55b`, `nvidia/nvidia/nemotron-3-nano-30b-a3b` | None |
| **Local NIM microservice** | `NEMOCLAW_PROVIDER=compatible`, `COMPATIBLE_API_KEY` | `nim-local/nvidia/nemotron-3-nano-30b-a3b` | 24 GB+ VRAM |
| **Ollama** (experimental) | `NEMOCLAW_PROVIDER=ollama`, `NEMOCLAW_MODEL=nemotron-3-nano:30b` | managed by NemoClaw | 24 GB+ VRAM |

Hosted endpoints are OpenAI-compatible at `https://integrate.api.nvidia.com/v1`; Super and Ultra carry 1M-token context. Model role assignment in the profile: **Super 120B** for triage/correlation/planning/response, **Ultra 550B** for deep investigation, **Nano 30B** for heartbeats and reporting. Embeddings for memory search run locally (GGUF) — nothing leaves the NVIDIA path.

Local NIM launch:

```bash
docker run --gpus all -p 8000:8000 \
  -e NGC_API_KEY=$NGC_API_KEY \
  nvcr.io/nim/nvidia/nemotron-3-nano-30b-a3b:latest

curl http://127.0.0.1:8000/v1/models   # served id MUST match the profile's model "id"
```

Ollama path (Ollama must be running before the installer; on WSL2 set `OLLAMA_HOST=0.0.0.0`):

```bash
ollama pull nemotron-3-nano:30b
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_NON_INTERACTIVE=1 NEMOCLAW_PROVIDER=ollama \
  NEMOCLAW_MODEL=nemotron-3-nano:30b bash
```

## Network Policy Tier

After sandbox creation NemoClaw asks which policy tier to apply: **Restricted**, **Balanced** (development presets: PyPI, npm, GitHub, Hugging Face), or **Open**. For a SOC deployment choose **Restricted** and allowlist only:

| Endpoint | Why |
|---|---|
| `MCP_URL` (Tailscale IP:3000) | Wazuh MCP server — 55 tools |
| `AUTOPILOT_RUNTIME_URL` | Case/plan API, two-tier approvals, webhooks |
| `integrate.api.nvidia.com` | Hosted Nemotron (omit if fully local) |
| Slack endpoints (optional) | Approval channel |

The SOC agents never install packages at runtime — leave developer egress off.

## Apply the Autopilot Configuration

NemoClaw provisions a **fresh** OpenClaw inside the sandbox; apply the profile afterwards:

```bash
nemoclaw wazuh-autopilot connect

# Inside the sandbox:
cp nemoclaw/openclaw-nemoclaw.json ~/.openclaw/openclaw.json
mkdir -p ~/.openclaw/wazuh-autopilot
cp -r openclaw/agents ~/.openclaw/wazuh-autopilot/

openclaw models scan       # MANDATORY — registers tool-calling capability for
                           # openai-completions providers; skipping it makes
                           # agents emit tool calls as plain text and stall
openclaw doctor --fix
```

## Verify

```bash
nemoclaw list                        # installed sandboxes
nemoclaw wazuh-autopilot status      # sandbox, provider, model, inference.local, GPU
nemoclaw launch wazuh-autopilot      # dashboard: 127.0.0.1:18789 (authenticated)

# Smoke-test inside the sandbox:
openclaw agent --agent wazuh-triage --local -m "status check" --session-id smoke
```

## Heartbeat Cost on Local GPU (important)

NemoClaw typically runs inference on a **local** GPU (DGX Spark/Station, RTX PRO, or a NIM on your own card). That makes agent **heartbeats** — which run inference on a timer even when there are zero alerts — the dominant idle load: the GPU never returns to baseline. Because NemoClaw runs the same OpenClaw agents, the same tuning applies, and `openclaw-nemoclaw.json` already ships the relaxed defaults (triage + correlation at `30m`).

For a quiet SOC on local hardware, go **fully event-driven** — set both per-agent heartbeats to `"0m"`:

```json5
// wazuh-triage / wazuh-correlation in openclaw-nemoclaw.json
"heartbeat": { "every": "0m" }
```

Dropped webhooks are still recovered by the runtime's zero-inference stalled-pipeline detector, so the node returns to idle the moment a case closes. Full details, math, and profiles: **[HEARTBEATS_AND_COST.md](HEARTBEATS_AND_COST.md)**.

## Scaling to a Swarm

Run multiple isolated sandboxes behind the same Runtime API for fleet-style operation:

```bash
NEMOCLAW_SANDBOX_NAME=wazuh-autopilot-2 ... bash   # repeat installer per sandbox
```

Each sandbox is independently policed, snapshotted, and rollback-able; every response action from every sandbox still funnels through the single Policy Guard gate and two-tier human approval.

> **Runtime-level fixes apply automatically.** Case/plan state lives in the shared Runtime Service, so fixes like *terminal-case grouping exclusion* and *plan-expiry persistence* (issue #33) are enforced by the Runtime API for NemoClaw exactly as for OpenClaw and Hermes — no per-sandbox change needed.

## Hermes Under NemoClaw

```bash
nemohermes onboard
```

runs the [Hermes profile](HERMES_DEPLOYMENT.md) inside OpenShell. The NVIDIA-stack rule applies unchanged: use the NVIDIA `custom` endpoint block in `hermes/config.yaml.example` (Nemotron via `integrate.api.nvidia.com/v1` or local NIM).

## Related NVIDIA Ecosystem

- **[Nemotron](https://developer.nvidia.com/nemotron)** — the open model family powering all inference here
- **[NIM](https://developer.nvidia.com/nim)** — TensorRT-LLM inference microservices for self-hosting
- **[NeMo](https://developer.nvidia.com/nemo)** — fine-tune Nemotron on your alert corpus (e.g., a triage-tuned Nano)
- **NeMo Guardrails / NeMo Agent Toolkit** — optional programmable rails and agent profiling
- **OpenShell** — the sandbox runtime NemoClaw is built on

## Upgrading / Uninstalling

```bash
npm update -g nemoclaw                          # upgrade (npm install)
docker pull ghcr.io/nvidia/nemoclaw:latest      # upgrade (docker install)

npm uninstall -g nemoclaw                       # uninstall CLI
rm -rf ~/.nemoclaw                              # remove all user data (optional)
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Agents emit tool calls as plain text; cases never advance | Run `openclaw models scan` inside the sandbox |
| `404` from inference | Model id mismatch — compare `curl .../v1/models` output with the `id` fields in `openclaw-nemoclaw.json` |
| Webhooks never arrive | `AUTOPILOT_RUNTIME_URL` missing from the OpenShell network allowlist |
| Installer exits in CI | Add `NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 NEMOCLAW_NON_INTERACTIVE=1` |
| Ollama provider not detected | Start Ollama before the installer; on WSL2 set `OLLAMA_HOST=0.0.0.0` |
| CI fails "NemoClaw profile is NVIDIA-stack only" | A non-NVIDIA provider/key/model was added to `nemoclaw/openclaw-nemoclaw.json` — that's the rule working as intended |
