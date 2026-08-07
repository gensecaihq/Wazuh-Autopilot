# Heartbeats & Inference Cost

Wazuh Autopilot is **event-driven**: a Wazuh alert triggers a webhook, which wakes the right agent, which advances the case. **Heartbeats** are a separate, timer-based safety net — agents that wake on a fixed interval to sweep for work even when no webhook fired.

Heartbeats are useful, but they run LLM inference **on a timer regardless of whether there is anything to do**. On paid APIs that is continuous token spend; on a small local model (e.g. `llama3.1:8b` on an RTX 3060) it keeps the GPU busy and the node never returns to idle. This is the single biggest idle cost in a quiet SOC, and it's the subject of [issue #33](https://github.com/gensecaihq/Wazuh-Autopilot/issues/33).

This guide explains exactly what runs, what it costs, and how to tune it — including a fully **event-driven** mode with zero idle inference.

## What actually heartbeats

OpenClaw's rule (important, and easy to get wrong):

> **If _any_ agent declares its own `heartbeat` block, only those agents run heartbeats.** The shared `agents.defaults.heartbeat` block then serves only as the merge template — it does **not** broadcast to every agent.

In the shipped configs, only **triage** and **correlation** declare `heartbeat` blocks. So:

- **Triage** and **correlation** heartbeat.
- Investigation, response-planner, policy-guard, and responder **never** heartbeat — they are purely reactive to webhooks.
- Reporting is driven by **cron** (`openclaw cron add`), not a heartbeat.

## The idle-inference math

Idle inference = heartbeat runs per hour when there are **zero** alerts.

| Config | Triage | Correlation | Idle runs/hour | Idle runs/day |
|---|---|---|---|---|
| **Old defaults** (pre-fix) | every 10m (6/h) | every 5m (12/h) | **18** | 432 |
| **Current defaults** (30m each) | every 30m (2/h) | every 30m (2/h) | **4** | 96 |
| **Event-driven** (`0m` each) | disabled | disabled | **0** | 0 |

The current defaults cut idle inference by ~78% versus the old ones, with no loss of recovery (see below). Event-driven removes it entirely.

> Earlier drafts of this analysis counted all seven agents (~28/h). That was wrong: because triage and correlation declare heartbeat blocks, the other five agents don't heartbeat at all. The real idle figure is the two-agent number above.

## Why relaxing heartbeats is safe: the runtime already recovers stuck work

Heartbeats are **not** how the pipeline normally advances — webhooks are. Their only unique job is catching a case whose webhook was dropped. The **runtime service already does this server-side, with zero LLM inference**:

- **Stalled-pipeline detector** (`STALLED_PIPELINE_ENABLED`, default on) — every 5 minutes it scans for cases stuck in a transient status past a threshold (default 30 min) and **re-dispatches the correct webhook**, with backoff. Pure Node.js, no model call.
- **Crash recovery** — plans stuck in `EXECUTING` are reset on startup.
- **Auto-close** — executed cases close after a grace period.

So a dropped webhook is recovered by the stalled detector within minutes whether or not heartbeats run. Heartbeats become a thin extra layer, not the engine — which is why 30 min (or off) is safe.

## Choosing a profile

Set the interval per agent in `openclaw.json` → `agents.list[].heartbeat.every`. `"0m"` disables an agent's heartbeat (it's a valid duration string; `"heartbeat": false` or `{ "enabled": false }` is **not** valid and will fail OpenClaw's strict schema).

### 1. Event-driven — recommended for small local models & paid APIs

Zero idle inference. The node returns to baseline the moment a case is closed. Dropped webhooks are still recovered by the stalled-pipeline detector.

```json5
// wazuh-triage
"heartbeat": { "every": "0m" }
// wazuh-correlation
"heartbeat": { "every": "0m" }
```

Keep the runtime's stalled detector on (it is, by default). Optionally tighten it so recovery is faster without any inference:

```bash
STALLED_PIPELINE_CHECK_INTERVAL_MS=120000   # scan every 2 min
STALLED_PIPELINE_THRESHOLD_MINUTES=10       # re-dispatch after 10 min stuck
```

### 2. Balanced — the shipped default

Triage and correlation sweep every 30 min. ~4 idle inferences/hour. A light safety net on top of the stalled detector.

```json5
"heartbeat": { "every": "30m" }
```

### 3. High-assurance — high-volume SOC on cheap/local inference

Faster sweeps where idle cost is not a concern (e.g. a dedicated GPU, or a cheap fast model like Groq/Nemotron Nano).

```json5
// wazuh-triage
"heartbeat": { "every": "10m" }
// wazuh-correlation
"heartbeat": { "every": "5m" }
```

## Cost impact by deployment

| Deployment | Heartbeat cost signal | Recommended profile |
|---|---|---|
| Paid API (OpenRouter/Anthropic/etc.) | Token spend accrues 24/7 even at idle | Event-driven or Balanced |
| Small local model (e.g. RTX 3060 + `llama3.1:8b`) | GPU never idles; high sustained load | **Event-driven** |
| Dedicated GPU / cheap fast model | Negligible | Balanced or High-assurance |
| NVIDIA NemoClaw (Nemotron Nano) | Local GPU load | Event-driven or Balanced |

## Reporting is on cron, not heartbeats

Scheduled reports (daily digests, weekly summaries) are time-driven and should stay on cron, which fires once at the scheduled time instead of polling:

```bash
openclaw cron add --schedule "0 8 * * *" --agent wazuh-reporting --name "daily-digest"
openclaw cron add --schedule "0 9 * * 1" --agent wazuh-reporting --name "weekly-summary"
```

## Quick checklist

- Small local model or paid API and a quiet SOC? → set triage + correlation to `"0m"` (event-driven).
- Want a light safety net? → leave them at `30m` (shipped default).
- Worried about dropped-webhook latency with heartbeats off? → tighten `STALLED_PIPELINE_*` instead — it recovers cases with **no** inference.
- Reports → cron, never a fast heartbeat.

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — event-driven pipeline, stalled detector, control plane
- [AGENT_CONFIGURATION.md](AGENT_CONFIGURATION.md) — agent config and `HEARTBEAT.md` files
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — operational issues
- [RUNTIME_API.md](RUNTIME_API.md) — `STALLED_PIPELINE_*` and other env knobs
