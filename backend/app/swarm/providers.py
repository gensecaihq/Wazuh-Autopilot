"""Model provider factory: Bedrock, Anthropic, OpenAI-compatible, vLLM, LiteLLM, Ollama, Demo."""

from typing import Any


def build_model(settings: dict, override: dict | None = None):
    cfg = dict(settings)
    if override:
        cfg.update({k: v for k, v in override.items() if v})
    provider = (cfg.get("provider") or "bedrock").lower()
    model_id = cfg.get("model_id") or ""
    temperature = cfg.get("temperature")
    max_tokens = int(cfg.get("max_tokens") or 4096)
    api_key = cfg.get("api_key") or ""
    base_url = (cfg.get("base_url") or "").rstrip("/")

    if provider == "bedrock":
        from strands.models import BedrockModel

        kwargs: dict[str, Any] = {"model_id": model_id or "global.anthropic.claude-sonnet-5",
                                  "region_name": cfg.get("region") or "us-east-1", "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        if cfg.get("guardrail_id"):
            kwargs.update(guardrail_id=cfg["guardrail_id"], guardrail_version=cfg.get("guardrail_version") or "DRAFT",
                          guardrail_trace="enabled")
        return BedrockModel(**kwargs)

    params: dict[str, Any] = {"max_tokens": max_tokens}
    if temperature is not None:
        params["temperature"] = float(temperature)

    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(client_args={"api_key": api_key}, model_id=model_id or "claude-sonnet-5",
                              max_tokens=max_tokens, params={k: v for k, v in params.items() if k != "max_tokens"})

    if provider in {"openai", "vllm", "nvidia_nim"}:
        from strands.models.openai import OpenAIModel

        client_args: dict[str, Any] = {"api_key": api_key or "EMPTY"}
        if base_url:
            client_args["base_url"] = base_url
        elif provider == "vllm":
            client_args["base_url"] = "http://vllm:8000/v1"
        elif provider == "nvidia_nim":
            client_args["base_url"] = "https://integrate.api.nvidia.com/v1"
        return OpenAIModel(client_args=client_args,
                           model_id=model_id or {"vllm": "Qwen/Qwen3-32B", "nvidia_nim": "nvidia/nemotron-3-super-120b-a12b"}.get(
                               provider, "gpt-5.4"),
                           params=params)

    if provider == "litellm":
        from strands.models.litellm import LiteLLMModel

        client_args = {}
        if api_key:
            client_args["api_key"] = api_key
        if base_url:
            client_args["api_base"] = base_url
        return LiteLLMModel(client_args=client_args, model_id=model_id or "openai/gpt-5.4", params=params)

    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        # Ollama defaults to a 2048-token context, far too small for multi-step tool calling.
        kwargs = {"model_id": model_id or "qwen3:32b", "max_tokens": max_tokens,
                  "options": {"num_ctx": int(cfg.get("context_window") or 32768)}}
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        return OllamaModel(base_url or "http://ollama:11434", **kwargs)

    if provider == "demo":
        import os

        from .demo_model import DemoModel

        lo, _, hi = os.getenv("AUTOPILOT_DEMO_LATENCY_MS", "350,1100").partition(",")
        return DemoModel(model_id=model_id or "autopilot-demo-1",
                         latency=(int(lo) / 1000, int(hi or lo) / 1000))

    raise ValueError(f"Unknown model provider '{provider}'")
