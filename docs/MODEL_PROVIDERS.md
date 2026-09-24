# Model Providers

The swarm-wide default model is set in **Settings → Models** (or seeded from `MODEL_PROVIDER` / `MODEL_ID` / `MODEL_BASE_URL` / `MODEL_API_KEY`). Any agent can override it on its **Config** tab, for example a small local model for triage and a frontier model for investigation and response planning. **Test model** sends a one-line prompt through the configured provider.

| Provider | Fields | Notes |
|---|---|---|
| **Amazon Bedrock** | model ID, region, optional Guardrail ID/version | IAM credentials (task or instance role on AWS; `AWS_PROFILE` or keys locally). A Guardrail applies to every model call. Needs `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`. |
| **Anthropic** | model ID, API key | |
| **OpenAI-compatible** | base URL, model ID, API key | OpenAI, Azure OpenAI, or any compatible endpoint |
| **NVIDIA NIM** | base URL, model ID, API key | Nemotron and other NIM models on build.nvidia.com (default `nvidia/nemotron-3-super-120b-a12b`), or a self-hosted NIM: point the base URL at it |
| **vLLM** | base URL, model ID | Self-hosted GPU inference (details below) |
| **LiteLLM** | model ID, optional base URL, API key | SDK routing (`bedrock/…`, `azure/…`, `vertex_ai/…`) or a LiteLLM proxy |
| **Ollama** | base URL, model ID, context window | Local and air-gapped (details below) |
| **Demo** | none | Scripted and deterministic. For demos and CI; no reasoning |

Pricing fields (USD per million input/output tokens) drive the cost figures in Runs, Agent Health and the Command Center.

Pick models with reliable multi-step tool calling. The swarm makes 5–10 tool calls per agent per incident. Models under ~14B parameters tend to lose track of multi-step procedures and are best kept for triage or testing.

## vLLM

```bash
docker compose --profile vllm up -d        # needs an NVIDIA GPU; set VLLM_MODEL and HUGGING_FACE_HUB_TOKEN in .env
```

Then **Settings → Models → vLLM**, base URL `http://vllm:8000/v1`, model ID matching `--model`. The compose service starts vLLM with `--enable-auto-tool-choice --tool-call-parser hermes`, which is right for Qwen models. Change the parser for other families:

| Parser | Model families |
|---|---|
| `hermes` | Qwen3, Qwen2.5, NousResearch Hermes |
| `llama3_json` | Llama 3.1 / 3.2 / 3.3 |
| `mistral` | Mistral, Mixtral |
| `deepseek_v32` | DeepSeek-V3, DeepSeek-R1 |

Tested sizes: Qwen3 32B (~64 GB VRAM FP16, the best balance), Llama 3.3 70B (~140 GB, deeper investigation), Qwen3 8B (~14 GB, testing only). Use `--tensor-parallel-size` for multi-GPU and set `--max-model-len` to at least 32k.

## LiteLLM

Without a proxy, set the model ID to a LiteLLM route (e.g. `bedrock/global.anthropic.claude-sonnet-5`) and put credentials in the environment. With the proxy:

```bash
docker compose --profile litellm up -d     # edit litellm/config.yaml first
```

Then set base URL `http://litellm:4000` and model ID `soc-default` (or another `model_name` from the config).

## Ollama and air-gapped deployments

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull qwen3:32b
```

Then **Settings → Models → Ollama**, base URL `http://ollama:11434`. Autopilot sets Ollama's context window to **32768** tokens by default (the "Context window" field). Ollama's own default of 2048 is too small for tool calling and makes agents drop instructions or print raw JSON.

For a fully offline install:

1. Build or pull the images (`wazuh-autopilot`, `postgres:16-alpine`, `ollama/ollama`) on a connected machine and move them with `docker save` / `docker load`.
2. Pre-pull the Ollama model and copy the `ollama-data` volume.
3. Keep the Wazuh MCP Server inside the enclave, and drop or disable its `web_search` toolset (it's the only tool that sends data off-box).
4. Leave OTLP export empty or point it at an in-enclave collector.

Nothing else in the platform calls out to the internet.

## Model-provider policy

Use pay-per-token API keys, not consumer subscription OAuth tokens. Several providers prohibit using subscription credentials in third-party tools.
