# Threat Hunter Agent -- Heartbeat (Scheduled Hunt)

**IMPORTANT:** You do NOT have `exec` permissions. Use ONLY the `web_fetch` tool for all HTTP requests.

This runs on a **low-frequency** schedule (default heartbeat every 6h; a daily cron is equally valid). Hunting is proactive and inference-costly, so broaden depth per run, not frequency — see docs/HEARTBEATS_AND_COST.md. Run ONE focused hunt per cycle, rotating the catalog for coverage. Follow each step in order.

### 1. Select a hypothesis
Pick the next hypothesis from the hunt catalog (AGENTS.md) or the MEMORY.md backlog, prioritizing techniques not hunted recently (check the ATT&CK Coverage Log) and those relevant to crown-jewel assets / current CTI.

### 2. Baseline, then hunt
Establish "normal" for the behavior over a longer window, then query the recent window for deviations (see TOOLS.md). Keep result sets bounded.

### 3. Triage candidates
For each candidate, rule out benign explanations and assign a suspicion level (confirmed / high / medium / low) with rationale. Rare is not the same as malicious.

### 4. Act with knowledge
- **confirmed / high** → escalate: annotate an existing case via `web_fetch` `update-case`, or set `escalate: true` in the report for a new case.
- **repeatable logic** → populate `recommend_detection` for the Detection Engineer.
- **nothing found** → record it as coverage (a clean hunt is a valid result).

### 5. Store the hunt report
Invoke `web_fetch` to `store-report` with `type=hunt` — hypothesis, data examined, result, findings, detection recommendation, and coverage entry. Do this every cycle, including clean hunts.

### 6. Update coverage & backlog
Record the technique + outcome in MEMORY.md's ATT&CK Coverage Log; add any new hypotheses surfaced during the hunt to the backlog.

### 7. Log heartbeat summary
Record: hypothesis hunted, technique, records examined, findings, escalations, detections recommended, processing duration.
