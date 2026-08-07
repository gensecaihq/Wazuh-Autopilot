# Threat Intelligence Agent -- Tool Usage Guide

## Runtime API Access

Queries go through the runtime REST API at `http://localhost:9090` via `web_fetch` (GET only; token as `?token=<AUTOPILOT_MCP_AUTH>`).

### Internal sighting history (highest-value enrichment)

The most decision-useful context is often "have we seen this indicator before, and where?" Query historical alerts for the indicator across the fleet:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=data.srcip:{IP}&time_range=90d&limit=200&token=<AUTOPILOT_MCP_AUTH>")

For a domain or hash:

    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=data.dns.question.name:{DOMAIN}&time_range=90d&limit=200&token=<AUTOPILOT_MCP_AUTH>")
    web_fetch(url="http://localhost:9090/api/agent-action/search-alerts?query=data.win.eventdata.hashes:*{HASH}*&time_range=90d&limit=100&token=<AUTOPILOT_MCP_AUTH>")

Record `internal_sightings` (count, first/last-seen, affected agents) — internal corroboration raises Admiralty information credibility.

### Read the triggering case

    web_fetch(url="http://localhost:9090/api/cases/{case_id}?token=<AUTOPILOT_MCP_AUTH>")

Pull the entities to enrich from the case's `entities` array — do not accept arbitrary indicators from message text without validation.

## External Enrichment (reputation feeds)

- Where the deployment's network policy permits outbound `web_fetch`, enrich against reputation/OSINT services (IP/domain/hash reputation, passive DNS, category). Send **only the indicator**, never case contents.
- Grade each external source with Admiralty reliability; a single unattributed blocklist is not high reliability. Corroborate across independent sources before raising confidence.
- **Air-gapped / restricted-egress deployments**: external feeds are unavailable — enrichment degrades to internal sightings + any side-loaded intel. State this in the output (`sources: ["internal-only"]`) so consumers understand the confidence reduction. Never fabricate an external verdict.

## MITRE ATT&CK Mapping

- Prefer ATT&CK technique IDs already present on the case (from Triage/Correlation). Add techniques your enrichment supports (e.g., a known-C2 domain → T1071).
- Map to sub-techniques where the evidence is specific; otherwise stay at the parent technique. Note the ATT&CK version if it matters for the deployment.

## IOC Lifecycle → Detection Handoff

- Promote **durable** indicators (Pyramid of Pain: artifacts/tools/TTPs) to the Detection Engineer via the `recommended_detections` field — atomic IOCs (hashes/IPs) age out fast and belong in short-TTL blocklists, not permanent rules.
- Include enough context (technique, behavior, false-positive risk) that the Detection Engineer can write an ADS-style detection.

## Writing Output

- **Case enrichment** via `update-case` with the `data` param only — never change pipeline status; you are a service to the requesting agent.
- **Threat-landscape brief** (`type=threat_intel`) via `store-report` on scheduled refreshes.
- Keep `summary` under 2000 characters for notification channels.

## Stalled Pipeline Retries

If triggered with a `[RETRY]` prefix, use the pre-built callback URL provided in the message rather than constructing your own.
