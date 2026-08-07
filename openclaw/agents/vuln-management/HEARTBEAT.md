# Vulnerability Management Agent -- Heartbeat (Scheduled Sweep)

**IMPORTANT:** You do NOT have `exec` permissions. Use ONLY the `web_fetch` tool for all HTTP requests.

This runs on a low-frequency schedule (default heartbeat every 12h; a daily cron is equally valid — vulnerability data changes slowly, so keep this infrequent to control inference cost, per docs/HEARTBEATS_AND_COST.md). Follow each step in order.

### 1. Pull current + baseline vulnerability volume
Query the last 24h and last 7d of `vulnerability-detector` alerts (see TOOLS.md). Compute the 7-day daily average for spike comparison.

### 2. Prioritize the backlog
Apply the risk-based model (KEV → EPSS → CVSS + environmental → SSVC) from AGENTS.md across all current detections. Resolve each to an SSVC decision and an SLA.

### 3. Detect spikes
Flag a detection spike (24h count > 2× the 7-day average, or any new KEV on a production asset) or an exploitation spike (exploitation-style alerts matching a vulnerable package on the same asset). If confirmed, follow PB-005.

### 4. Escalate exploited criticals
For KEV / SSVC-Act items — especially on internet-facing or crown-jewel assets — annotate the relevant case (if one exists) with `escalate_containment: true` so the Response Planner can propose compensating controls while patching is scheduled.

### 5. Store the posture report
Invoke `web_fetch` to `store-report` with `type=vulnerability` — top exposures, KEV count, SSVC distribution, SLA compliance, spike status, and trend vs. the previous run.

### 6. Log sweep summary
Record: vulnerabilities assessed, KEV count, SSVC-Act count, assets affected, spikes detected, escalations raised, processing duration.
