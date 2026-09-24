import type { ModelSettings, ProviderInfo } from "@/api/types";

/** Fallback used when /settings/providers isn't reachable (e.g. during first-run setup). */
export const FALLBACK_PROVIDERS: ProviderInfo[] = [
  {
    id: "bedrock",
    label: "Amazon Bedrock",
    description: "Default for enterprise. IAM credentials, in-account inference, optional Bedrock Guardrails.",
    fields: ["model_id", "region", "guardrail_id", "guardrail_version"],
    defaults: { model_id: "global.anthropic.claude-sonnet-5", region: "us-east-1" },
    local: false,
  },
  {
    id: "anthropic",
    label: "Anthropic",
    description: "Claude models via the Anthropic API.",
    fields: ["model_id", "api_key"],
    defaults: { model_id: "claude-sonnet-5" },
    local: false,
  },
  {
    id: "openai",
    label: "OpenAI-compatible",
    description: "OpenAI, Azure OpenAI, NVIDIA NIM or any OpenAI-compatible endpoint.",
    fields: ["base_url", "model_id", "api_key"],
    defaults: { base_url: "https://api.openai.com/v1", model_id: "gpt-5.4" },
    local: false,
  },
  {
    id: "nvidia_nim",
    label: "NVIDIA NIM",
    description: "NVIDIA Nemotron and other NIM models via build.nvidia.com, or a self-hosted NIM.",
    fields: ["base_url", "model_id", "api_key"],
    defaults: { base_url: "https://integrate.api.nvidia.com/v1", model_id: "nvidia/nemotron-3-super-120b-a12b" },
    local: false,
  },
  {
    id: "vllm",
    label: "vLLM",
    description: "Self-hosted GPU inference through vLLM's OpenAI-compatible server.",
    fields: ["base_url", "model_id", "api_key"],
    defaults: { base_url: "http://vllm:8000/v1", model_id: "Qwen/Qwen3-32B" },
    local: true,
  },
  {
    id: "litellm",
    label: "LiteLLM",
    description: "Route through a LiteLLM proxy, or call 100+ providers directly.",
    fields: ["base_url", "model_id", "api_key"],
    defaults: { base_url: "http://litellm:4000", model_id: "openai/gpt-5.4" },
    local: false,
  },
  {
    id: "ollama",
    label: "Ollama",
    description: "Air-gapped local models. Nothing leaves the host.",
    fields: ["base_url", "model_id", "context_window"],
    defaults: { base_url: "http://ollama:11434", model_id: "qwen3:32b", context_window: 32768 },
    local: true,
  },
  {
    id: "demo",
    label: "Demo (scripted)",
    description: "Deterministic scripted model for demos and CI. No API key, no network.",
    fields: [],
    defaults: { model_id: "demo-soc-1" },
    local: true,
  },
];

export const FIELD_LABELS: Partial<Record<keyof ModelSettings, { label: string; placeholder?: string; secret?: boolean }>> = {
  model_id: { label: "Model ID" },
  base_url: { label: "Base URL", placeholder: "http://host:port/v1" },
  api_key: { label: "API key", secret: true },
  region: { label: "AWS region", placeholder: "us-east-1" },
  guardrail_id: { label: "Bedrock Guardrail ID (optional)" },
  guardrail_version: { label: "Guardrail version", placeholder: "DRAFT" },
  temperature: { label: "Temperature" },
  max_tokens: { label: "Max tokens" },
  context_window: { label: "Context window (tokens)", placeholder: "32768" },
};

export const AUTONOMY_LEVELS = [
  {
    id: "observe" as const,
    label: "Observe",
    tag: "L0",
    desc: "Agents triage and investigate only. No response actions are proposed.",
  },
  {
    id: "recommend" as const,
    label: "Recommend",
    tag: "L1",
    desc: "Agents propose actions. A human approves and a human executes (two-tier).",
  },
  {
    id: "supervised" as const,
    label: "Supervised",
    tag: "L2",
    desc: "A human approves. The platform executes and verifies automatically.",
  },
  {
    id: "autonomous" as const,
    label: "Autonomous",
    tag: "L3",
    desc: "Allow-listed, high-confidence actions on non-protected targets run automatically. Everything else is supervised.",
  },
];
