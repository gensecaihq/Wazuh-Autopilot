"""Runtime settings persisted in the database, one row per section."""

import copy
import secrets

from sqlalchemy.orm import Session

from .config import get_config
from .models import Setting

SECRET_FIELDS = {
    "wazuh": {"api_key"},
    "model": {"api_key"},
    "notifications": {"slack_webhook_url"},
    "observability": {"otlp_headers"},
    "ingestion": {"ingest_key"},
}

PROVIDERS = [
    {"id": "bedrock", "label": "Amazon Bedrock", "local": False,
     "description": "Claude, Nova, Llama and more through your AWS account. IAM auth, optional Guardrails.",
     "fields": ["model_id", "region", "guardrail_id", "guardrail_version"],
     "defaults": {"model_id": "global.anthropic.claude-sonnet-5", "region": "us-east-1"}},
    {"id": "anthropic", "label": "Anthropic", "local": False,
     "description": "Claude models via the Anthropic API.",
     "fields": ["model_id", "api_key"], "defaults": {"model_id": "claude-sonnet-5"}},
    {"id": "openai", "label": "OpenAI-compatible", "local": False,
     "description": "OpenAI, Azure OpenAI, NVIDIA NIM or any OpenAI-compatible endpoint.",
     "fields": ["base_url", "model_id", "api_key"], "defaults": {"base_url": "", "model_id": "gpt-5.4"}},
    {"id": "nvidia_nim", "label": "NVIDIA NIM", "local": False,
     "description": "NVIDIA Nemotron and other NIM models via build.nvidia.com, or a self-hosted NIM (set its base URL).",
     "fields": ["base_url", "model_id", "api_key"],
     "defaults": {"base_url": "https://integrate.api.nvidia.com/v1", "model_id": "nvidia/nemotron-3-super-120b-a12b"}},
    {"id": "vllm", "label": "vLLM", "local": True,
     "description": "Self-hosted GPU inference. Start vLLM with --enable-auto-tool-choice and a tool-call parser.",
     "fields": ["base_url", "model_id", "api_key"],
     "defaults": {"base_url": "http://vllm:8000/v1", "model_id": "Qwen/Qwen3-32B"}},
    {"id": "litellm", "label": "LiteLLM", "local": False,
     "description": "100+ providers through LiteLLM (SDK routing or a LiteLLM proxy base URL).",
     "fields": ["model_id", "base_url", "api_key"],
     "defaults": {"model_id": "openai/gpt-5.4", "base_url": ""}},
    {"id": "ollama", "label": "Ollama", "local": True,
     "description": "Local models, fully air-gapped. Pick a model with reliable tool calling (Qwen3, Llama 3.1+).",
     "fields": ["base_url", "model_id", "context_window"],
     "defaults": {"base_url": "http://ollama:11434", "model_id": "qwen3:32b", "context_window": 32768}},
    {"id": "demo", "label": "Demo (scripted)", "local": True,
     "description": "Deterministic scripted model for demos and CI. Calls real tools, costs nothing, reasons about nothing.",
     "fields": [], "defaults": {"model_id": "autopilot-demo-1"}},
]


def defaults() -> dict:
    cfg = get_config()
    provider = next((p for p in PROVIDERS if p["id"] == cfg.model_provider), PROVIDERS[0])
    return {
        "org": {"name": cfg.org_name, "timezone": "UTC", "logo_initials": "".join(w[0] for w in cfg.org_name.split()[:2]).upper()},
        "wazuh": {
            "mcp_url": cfg.wazuh_mcp_url, "api_key": cfg.wazuh_mcp_api_key, "verify_tls": True,
            "toolsets": ["alerts", "agents", "vulnerabilities", "analysis", "compliance", "system", "response"],
            "request_timeout_s": 30,
        },
        "model": {
            "provider": provider["id"],
            "model_id": cfg.model_id or provider["defaults"].get("model_id", ""),
            "base_url": cfg.model_base_url or provider["defaults"].get("base_url", ""),
            "api_key": cfg.model_api_key, "region": cfg.aws_region,
            "temperature": 0.2, "max_tokens": 4096, "guardrail_id": "", "guardrail_version": "DRAFT",
            "price_in_per_mtok": 3.0, "price_out_per_mtok": 15.0,
        },
        "ingestion": {
            "mode": "both" if cfg.demo_mode else "webhook", "poll_interval_s": 30, "min_level": 10,
            "ingest_key": cfg.ingest_key or secrets.token_urlsafe(24),
            "dedup_window_min": 10, "group_window_min": 60, "max_runs_per_hour": 30,
        },
        "notifications": {"slack_webhook_url": "", "email_to": "", "notify_on": ["critical_case", "approval_needed", "action_failed"]},
        "observability": {"otlp_endpoint": "", "otlp_headers": "", "prometheus_enabled": True, "trace_retention_days": 30},
        "swarm": {"max_handoffs": 12, "max_iterations": 16, "execution_timeout_s": 900, "node_timeout_s": 300, "max_concurrent_runs": 4},
        "policy": {
            "autonomy_level": "supervised" if cfg.demo_mode else "recommend",
            "action_rules": [],  # filled by seed from the action catalog
            "protected_targets": {"ips": ["127.0.0.1"], "hosts": ["dc-01", "wazuh-manager"], "users": ["root", "Administrator"], "agent_ids": ["000"]},
            "approval_expiry_minutes": 60, "require_two_person": False, "business_hours_only": False,
        },
        "setup": {"complete": cfg.demo_mode or bool(cfg.admin_password)},
    }


def get_section(db: Session, key: str) -> dict:
    row = db.get(Setting, key)
    base = defaults().get(key, {})
    if not row:
        return copy.deepcopy(base)
    merged = copy.deepcopy(base)
    merged.update(row.value or {})
    return merged


def set_section(db: Session, key: str, value: dict) -> dict:
    current = get_section(db, key)
    for field, v in value.items():
        # Masked secrets coming back from the UI mean "unchanged".
        if field in SECRET_FIELDS.get(key, set()) and isinstance(v, str) and v.startswith("••••"):
            continue
        current[field] = v
    row = db.get(Setting, key)
    if row:
        row.value = current
    else:
        db.add(Setting(key=key, value=current))
    db.flush()
    return current


def mask(key: str, value: dict) -> dict:
    out = dict(value)
    for field in SECRET_FIELDS.get(key, set()):
        v = out.get(field)
        if v:
            out[field] = "••••" + str(v)[-4:]
    return out


PUBLIC_SECTIONS = ["org", "wazuh", "model", "ingestion", "notifications", "observability", "swarm"]


def all_settings(db: Session, masked: bool = True) -> dict:
    return {k: (mask(k, get_section(db, k)) if masked else get_section(db, k)) for k in PUBLIC_SECTIONS}
