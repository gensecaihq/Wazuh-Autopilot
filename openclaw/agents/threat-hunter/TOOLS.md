# Threat Hunter Agent -- Tool Usage Guide

## Runtime API Access

All hunts run through the runtime REST API at `http://localhost:9090` via `web_fetch` (GET only; token as `?token=<AUTOPILOT_MCP_AUTH>`).

### Behavioral / TTP queries (the core of hunting)

Use `search-alerts` with field queries against the Wazuh Indexer. Examples aligned to the hunt catalog:

**LOLBin download/exec (T1105):**

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=data.win.eventdata.image:(*certutil.exe%20OR%20*bitsadmin.exe%20OR%20*mshta.exe)%20AND%20data.win.eventdata.commandLine:(*http*%20OR%20*urlcache*)&time_range=7d&limit=200&token=<AUTOPILOT_MCP_AUTH>")

**Suspicious parent→child (T1055/T1059):**

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=data.win.eventdata.parentImage:(*winword.exe%20OR%20*excel.exe)%20AND%20data.win.eventdata.image:(*cmd.exe%20OR%20*powershell.exe)&time_range=7d&limit=200&token=<AUTOPILOT_MCP_AUTH>")

**Encoded PowerShell (T1059.001):**

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=data.win.eventdata.commandLine:(*-enc*%20OR%20*FromBase64String*)&time_range=7d&limit=200&token=<AUTOPILOT_MCP_AUTH>")

**Anomalous authentication (T1078/T1021):**

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=rule.groups:authentication_success%20AND%20data.srcip:*&time_range=7d&limit=500&token=<AUTOPILOT_MCP_AUTH>")

### Host-level enrichment for candidates

Pull live process and port context for a suspect host (beaconing, persistence, lateral movement):

    web_fetch(url="http://localhost:9090/api/agent-action/get-agent?agent_id={id}&token=<AUTOPILOT_MCP_AUTH>")

## Baselining Technique

1. **Establish normal first.** Query a longer window (e.g., 30d) to learn the baseline for the behavior (which hosts normally run `powershell`, typical logon source→dest pairs, usual outbound destinations).
2. **Then find deviations** in the recent window (24h–7d) against that baseline.
3. **Frequency/rarity analysis** for C2: group outbound by destination and look for periodic, low-variance intervals (beaconing) or rare-destination + long-duration flows.
4. **Stack counting**: count occurrences of a value (e.g., parent→child pairs); the rare tail is where hunts pay off.

## Coverage Tracking

- Record every hunt's ATT&CK technique and outcome in the report and in MEMORY.md, so the team can see which techniques were hunted, when, and with what result (Hunting Maturity Model progression).
- Rotate the hunt catalog so coverage broadens over time rather than repeating the same one or two hunts.

## Cost Discipline

Hunting runs inference on a schedule. Keep it **low-frequency** (default heartbeat 6h, or a daily cron) and bounded (capped result sets, focused queries) — see docs/HEARTBEATS_AND_COST.md. Broaden depth, not frequency.

## Handoffs

- **Escalation**: annotate an existing case via `update-case` (data only), or flag `escalate: true` in the hunt report for a new case to be opened by a human.
- **Detection**: put repeatable logic in `recommend_detection` — the Detection Engineer turns it into a Wazuh/Sigma rule with FP analysis.
- **Reporting**: the `hunt` report feeds the SOC Manager's coverage view.

## Stalled Pipeline Retries

If triggered with a `[RETRY]` prefix, use the pre-built callback URL from the message rather than constructing your own.
