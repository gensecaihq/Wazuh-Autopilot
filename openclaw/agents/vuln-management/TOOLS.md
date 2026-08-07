# Vulnerability Management Agent -- Tool Usage Guide

## Runtime API Access

All Wazuh queries go through the runtime REST API at `http://localhost:9090` via `web_fetch` (GET only; token as `?token=<AUTOPILOT_MCP_AUTH>` on every request).

### Query vulnerability detections

Vulnerability findings surface as Wazuh alerts in the `vulnerability-detector` rule groups. Use `search-alerts`:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=rule.groups:vulnerability-detector&time_range=24h&limit=500&token=<AUTOPILOT_MCP_AUTH>")

Filter for critical severity or a specific agent:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=rule.groups:vulnerability-detector%20AND%20data.vulnerability.severity:Critical&time_range=7d&limit=200&token=<AUTOPILOT_MCP_AUTH>")

Key fields in each record: `data.vulnerability.cve`, `data.vulnerability.cvss.cvss3.base_score`, `data.vulnerability.cvss.cvss3.vector`, `data.vulnerability.severity`, `data.vulnerability.package.name`, `data.vulnerability.package.version`, `data.vulnerability.package.condition` (e.g., "less than 1.2.3"), `agent.id`, `agent.name`.

### Asset context

    web_fetch(url="http://localhost:9090/api/agent-action/get-agent?agent_id={id}&token=<AUTOPILOT_MCP_AUTH>")

Use `os`, `ip`, `groups`, and last-seen to infer exposure (internet-facing vs internal) and criticality. Cross-reference hostname/IP patterns from `_shared/USER.md` (critical asset ranges, DMZ, crown-jewel hosts).

### Detect exploitation attempts

Correlate vulnerable packages with exploitation-style alerts on the same asset:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=agent.id:{id}%20AND%20rule.groups:(exploit%20OR%20attack%20OR%20web)&time_range=24h&limit=100&token=<AUTOPILOT_MCP_AUTH>")

### Baseline for spike detection

Pull the 7-day vulnerability volume to compute the rolling daily average, then compare the last 24 h:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=rule.groups:vulnerability-detector&time_range=7d&limit=500&token=<AUTOPILOT_MCP_AUTH>")

## Prioritization Feeds (KEV / EPSS)

- **CISA KEV** and **EPSS** are external, authoritative signals. Where the deployment's network policy permits outbound `web_fetch`, retrieve them from their official sources and cache. In air-gapped deployments these feeds must be side-loaded; when unavailable, **fall back to CVSS + environmental context and mark KEV/EPSS as `unknown`** in your output — never fabricate a KEV flag or EPSS value.
- Prefer the CVSS vector already present in the Wazuh detection (`data.vulnerability.cvss.cvss3.vector`). Recompute the environmental score using asset exposure/criticality; do not alter the base score.

## Writing Output

- **Posture report** (`type=vulnerability`) via `store-report` — top exposures, KEV exposure count, SSVC distribution, SLA compliance, spike status.
- **Case annotation** via `update-case` (data param only, no status change) for exploited criticals that already have a case — set an `escalate_containment` flag so the Response Planner picks it up.
- Keep `summary` under 2000 characters for notification channels.

## Air-Gapped / Offline Notes

Without internet, KEV/EPSS enrichment degrades gracefully to CVSS + environmental scoring. Document in the report that exploit-intel feeds were unavailable so consumers understand the confidence reduction. Side-loading a dated KEV/EPSS snapshot restores full prioritization.

## Stalled Pipeline Retries

If triggered with a `[RETRY]` prefix, a prior run stalled and a pre-built callback URL is included in the message — call that URL with `web_fetch` rather than constructing your own.
