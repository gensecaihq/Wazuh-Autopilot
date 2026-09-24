import type { ModelSettings, ProviderInfo } from "@/api/types";
import { Field } from "@/components/ui";
import { FIELD_LABELS } from "@/lib/providers";

export function ModelFields({
  value,
  onChange,
  provider,
  disabled,
  showTuning,
}: {
  value: ModelSettings;
  onChange: (m: ModelSettings) => void;
  provider?: ProviderInfo;
  disabled?: boolean;
  showTuning?: boolean;
}) {
  const fields = provider?.fields ?? ["model_id"];
  if (!fields.length && !showTuning)
    return <p className="text-xs text-muted">No configuration needed. The demo model runs in-process with scripted SOC behavior.</p>;
  const set = (k: keyof ModelSettings, v: string | number) => onChange({ ...value, [k]: v } as ModelSettings);
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {fields.map((f) => {
        const meta = FIELD_LABELS[f] ?? { label: f };
        const raw = value[f];
        return (
          <Field key={f} label={meta.label}>
            <input
              className="input font-mono text-[13px]"
              type={meta.secret ? "password" : "text"}
              disabled={disabled}
              value={raw === null || raw === undefined ? "" : String(raw)}
              placeholder={meta.placeholder ?? (provider?.defaults[f] !== undefined ? String(provider.defaults[f]) : "")}
              onChange={(e) => set(f, f === "context_window" ? Number(e.target.value) : e.target.value)}
            />
          </Field>
        );
      })}
      {showTuning && (
        <>
          <Field label="Temperature" hint="Lower is more deterministic. 0.1–0.3 suits SOC work.">
            <input className="input" type="number" step="0.05" min={0} max={1} disabled={disabled} value={value.temperature} onChange={(e) => set("temperature", Number(e.target.value))} />
          </Field>
          <Field label="Max output tokens">
            <input className="input" type="number" min={256} step={256} disabled={disabled} value={value.max_tokens} onChange={(e) => set("max_tokens", Number(e.target.value))} />
          </Field>
          <Field label="Price per 1M input tokens (USD)" hint="Used for cost estimates.">
            <input className="input" type="number" step="0.01" min={0} disabled={disabled} value={value.price_in_per_mtok} onChange={(e) => set("price_in_per_mtok", Number(e.target.value))} />
          </Field>
          <Field label="Price per 1M output tokens (USD)">
            <input className="input" type="number" step="0.01" min={0} disabled={disabled} value={value.price_out_per_mtok} onChange={(e) => set("price_out_per_mtok", Number(e.target.value))} />
          </Field>
        </>
      )}
    </div>
  );
}
