---
name: ir-playbook-data-exfiltration
description: Incident-response playbook for suspected data exfiltration — archive staging, uploads to cloud storage, exfil over C2 or DNS, removable media and exposed cloud buckets; use when Wazuh flags staging or transfer indicators (e.g. rules 92212, 91846, 92038, 81101, 99548) or when volume/destination anomalies are reported. Most volume and DNS detections need custom rules — see section 1.
allowed-tools: get_wazuh_alerts search_security_events get_wazuh_agents check_agent_health get_agent_processes get_agent_ports get_case search_cases update_case add_entities link_mitre add_finding list_actions wazuh_check_blocked_ip wazuh_check_process wazuh_check_file_quarantine wazuh_check_user_status wazuh_check_agent_isolation
metadata:
  category: response
  display_name: IR Playbook — Data Exfiltration
  standards: [nist-800-61r3, sans-picerl, mitre-attack, mitre-d3fend, iso-27001-2022, pci-dss-4, nist-csf-2]
  version: "2.1"
---
# IR Playbook — Data Exfiltration

Severity **high → critical** depending on data classification and whether transfer is ongoing. Regulated data
(PII/PHI/cardholder) can start breach-notification clocks, so record timestamps precisely. Rule IDs are from the
stock Wazuh 4.14 ruleset (levels official). Full procedure, forensic commands and notification templates:
`references/playbook.md`.

## 1. Detection signals

Stock Wazuh coverage for exfiltration is thin: it detects **staging** and some **transfer tooling** on Windows,
cloud-provider findings, and USB storage. Volume thresholds and DNS tunnelling need network telemetry plus custom rules.

| Technique | Stock Wazuh rules (level) | Needs |
|---|---|---|
| T1560.001 Archive staging (Windows) | rules 92212 (L14, compression by PowerShell), 92210 (L6, compression in Users\Public), 91846 (L10, PowerShell .NET compression), 91825 (L4), 91821 (L4, archive of a filesystem search) | Sysmon Event ID 11, PowerShell/Operational |
| T1567.002 Exfil to cloud storage | rule 92038 (L12, connection to a cloud resource started by a script/binary) | Sysmon Event ID 1 |
| T1114 Email collection | rule 91845 (L10, Outlook add-in loaded by PowerShell) | PowerShell/Operational |
| T1052.001 Removable media | rule 81101 (L3, USB storage attached) | Linux kernel USB logs |
| T1537 / cloud exposure | rules 99855 (L12, S3 public read), 99856 (L12, S3 public write), 65061 (L3, GCP bucket permissions modified) | AWS Security Hub / GCP integrations |
| EDR telemetry (if integrated) | rules 99548 (L12), 99567 (L13), 99586 (L15) — Microsoft Graph "system is performing data exfiltration" | MS Graph integration |

Org-custom rules (the stock ruleset has none; create in range 100000–120000 and validate with `wazuh-logtest`):

| Behaviour | Suggested custom rule |
|---|---|
| T1041 / T1030 outbound volume (> 500 MB/h per host, or > 10 Mbps sustained 30 min) | `custom rule 100501` / `custom rule 100502` on firewall/NetFlow/Zeek logs, `<same_source_ip />` |
| T1048.003 DNS tunnelling (long/encoded labels, > 100 queries/min, Base64 in TXT) | `custom rule 100520`, `custom rule 100521`, `custom rule 100522` on DNS server or Zeek `dns.log` |
| Large archive in temp/staging dirs (Linux) | `custom rule 100530` — child of FIM rules 554, 550 on staging paths with a size threshold |
| Uploads to unsanctioned cloud storage / webmail | `custom rule 100550`, `custom rule 100551` on proxy logs with an allowlist of sanctioned domains |
| DLP policy violation | `custom rule 100560` on your DLP product's decoder |
| Uploads to non-approved S3 / Azure / GCP buckets | `custom rule 100570`, `custom rule 100571`, `custom rule 100572` on cloud audit logs |

The reference playbook contains example XML for each — adapt field names to your decoders and validate with `wazuh-logtest`.

High-confidence combinations: staging archive **then** outbound spike from the same host; DNS tunnelling from a host
with no business need for high DNS volume; departing-employee account.

## 2. Triage / investigation (investigation agent)

1. `get_wazuh_alerts` for the host (`agent_id`, `timestamp_start: "now-24h"`); `search_cases` on host/user/destination.
2. Answer:
   - What data? Classification of paths involved (finance, HR, source code, customer DB).
   - How much and where to (destination IP/domain/bucket, sanctioned or not)?
   - **Still happening?** Latest alert timestamps; `get_agent_ports` for live outbound connections.
   - Who? Role, recent HR flags, off-hours activity, first-time behaviour.
3. Host evidence: `get_agent_processes` (rclone, curl/wget loops, 7z/rar, cloud sync clients, PowerShell uploads);
   `search_security_events` for the destination across the fleet; look back for preceding intrusion (brute force,
   malware, privilege escalation). Destination reputation → hand off to threat-intel.
4. `add_entities` (host = victim, user = observed/attacker, destination ip/domain = attacker, staged paths as `file`),
   `link_mitre`, `update_case` (ongoing transfer of regulated data → critical; completed transfer of internal data → high).
5. Insider vs external changes the path: insider → HR/legal, preserve evidence quietly; external → active intrusion.
   `add_finding` with evidence and a containment **recommendation to response-planner**.

Decision tree: sanctioned destination → likely FP (confirm with owner, tune, close); unsanctioned, small, no sensitive
paths → medium; sensitive paths or > 1 GB finished → high; ongoing or preceded by intrusion → critical, contain now;
DNS tunnelling confirmed → critical regardless of volume (implies malware/C2).

## 3. Response (response-planner)

Evidence before disruption: connections, process list and file hashes must already be in findings. Check
`wazuh_check_blocked_ip` before proposing a block.

| Situation | Proposal |
|---|---|
| Transfer ongoing to external IP | `propose_action(type="block_ip", target=<dest ip>, params={"ip_address": <dest ip>, "agent_id": <host>})` (D3-ITF/D3-OTF) |
| Per-host firewall drop | `propose_action(type="firewall_drop", params={"agent_id": <host>, "ip_address": <ip>})` |
| Exfil tool running | `propose_action(type="kill_process", params={"agent_id": <host>, "process_id": <pid>})` |
| Staged archive on disk | `propose_action(type="quarantine_file", params={"agent_id": <host>, "file_path": <path>})` (D3-FEV) |
| Compromised or malicious account | `propose_action(type="disable_user", params={"agent_id": <host>, "username": <user>})` |
| Active intrusion with exfil | `propose_action(type="isolate_host", params={"agent_id": <host>})` (high risk; supervised) |

DNS-tunnel domains and cloud buckets can't be blocked by Wazuh active response — record them with `add_finding`
for the network/cloud team (DNS sinkhole, bucket policy, CASB).

## 4. Eradication and recovery

- Revoke tokens/keys used for the upload (cloud access keys, OAuth grants) — human task.
- Remove staging files and exfil tooling; rotate credentials of affected accounts.
- Confirm no further outbound anomalies for 72 h; tune DLP and egress rules.

## 5. Verification

The responder verifies executed actions (`wazuh_check_blocked_ip`, `wazuh_check_process`,
`wazuh_check_file_quarantine`, `wazuh_check_user_status`, `wazuh_check_agent_isolation`).

## 6. Evidence, compliance and records

- Chain of custody: who collected what, when, hash (ISO 27001 A.5.28) — in findings.
- Estimate exposure (classification, file count, volume, record count); this feeds notification decisions.
- Cardholder/health data involved → hand off to compliance for PCI DSS Req 10 / 12.10 and ISO A.5.24–A.5.28 mapping.
- `standard_refs` e.g. `MITRE-ATTACK:T1048.003`, `NIST-800-61r3:Respond`, `ISO-27001:A.5.26`.
- Hand off to reporting for a legal/privacy-ready timeline; missing custom rules → hand off to detection-engineer.

## Escalation

| Condition | Escalate to |
|---|---|
| Regulated data confirmed exfiltrated | CISO, legal, privacy officer (notification clocks) |
| Insider suspected | HR + legal; restrict case visibility |
| Ongoing transfer, containment refused by policy | SOC lead for manual approval |
