---
name: wazuh-cloud-container
description: Interpret Wazuh cloud and container alerts — AWS (CloudTrail, GuardDuty, VPC Flow, Security Hub), Azure, GCP, Microsoft Graph, Office 365, GitHub and Docker — with their key fields, normal baselines and pivots; use for any alert from a cloud or container integration.
allowed-tools: get_wazuh_alerts search_security_events get_alerts_aggregated get_wazuh_agents get_wazuh_rules_summary get_case search_cases update_case add_entities add_finding link_mitre
metadata:
  category: investigation
  display_name: Wazuh Cloud and Container
  standards: [mitre-attack, nist-csf-2, cis-v8-1, iso-27001-2022]
  version: "1.0"
---
# Wazuh Cloud and Container

Cloud and SaaS logs reach Wazuh through integration modules on the manager (or a collector agent), so
the `agent` is usually the manager or collector — the real actor is in `data.*`. Always pivot on the
identity, source IP and resource from `data`, not on `agent.name`.

## Integrations in the stock ruleset

| Source | Groups | Key rules (level) | Key fields |
|---|---|---|---|
| AWS CloudTrail | `amazon`, `aws`, `aws_cloudtrail` | rule 80202 (level 3, API call), rule 80203 (level 4, API call with error), rule 80253 (level 3, console login success), rule 80254 (level 5, console login failed), rule 80255 (level 10, possible break-in attempt), rule 80252 (level 10, high number of deleted objects) | `data.aws.eventName`, `eventSource`, `userIdentity.arn`, `sourceIPAddress`, `awsRegion`, `errorCode` |
| AWS GuardDuty | `aws_guardduty` | rules 80301, 80302, 80303 (levels 3, 6, 10 by finding severity); with remote IP: rules 80305, 80306, 80307 | `data.aws.title`, `service.action.actionType`, `severity`, resource |
| AWS VPC Flow / WAF / Config / Inspector / Macie / KMS / Security Hub | `aws_vpcflow`, `aws_waf`, `aws_config`, `aws_inspector`, `aws_macie`, `aws_kms`, `aws_security_hub` | By group | Service-specific under `data.aws.*` |
| Azure | `azure` | rule 87802 (level 3, "Azure: AD $(activityDisplayName)"), rule 87811 (level 3, Log Analytics operation) | `data.activityDisplayName`, operation, caller |
| Microsoft Graph (Defender/Entra alerts & incidents) | `ms-graph` | rule 99503 (level 6, alert/incident not resolved and not a false positive) | alert title, severity, entities |
| GCP | `gcp` | rule 65053 (level 3, firewall rule created), rule 65054 (level 3, firewall rule deleted), rule 65056 (level 3, logging bucket deleted), rule 65057 (level 3, logging sink deleted), rule 65070 (level 3, new service account created) | `data.gcp.protoPayload.*`, principal, resource |
| Office 365 | `office365` | rule 91556 (level 12, phishing/malware events from Exchange Online Protection / Defender), rule 91700 (level 14, malware detected in file), rule 91724 (level 10, suspicious download activity by user) | `data.office365.UserId`, `Operation`, `ClientIP`, `Workload` |
| GitHub | `github` | rule 91152 (level 9, environment actions secret removed), rule 91197 (level 7, organization actions secret created); secret-scanning groups `git_secret_scanning`, `git_repository_secret_scanning` | `data.github.actor`, `action`, `repo`, `org` |
| Docker (docker-listener) | `docker` | rule 87907 (level 3, command launched in container), rule 87908 (level 5, shell session started in container), rule 87910 (level 3, file copied from host into container), rule 87902 (level 5, container destroyed) | `data.docker.Actor.Attributes.name`, `image`, `Action` |

**Kubernetes audit logs are not covered by the stock ruleset** (only EKS controls via Security Hub).
Monitoring kube-apiserver audit events needs a custom decoder and custom rules (example to create:
custom rule 100500 for `pods/exec` by a non-admin identity). Say so rather than implying coverage.

Many cloud rules are level 3 by design — the stock ruleset records activity and leaves importance to
context. A level-3 `DeleteTrail`, `StopLogging`, logging-sink deletion or root-account login matters far
more than its level.

## What "normal" looks like (baseline before judging)

- Identities: known automation roles and CI users make most API calls at steady rates; humans log in
  from known IP ranges and regions.
- Use `get_alerts_aggregated` and `search_security_events` with the identity or IP as `query` over
  `7d` to establish prevalence before calling an action anomalous.

## High-signal patterns

| Pattern | Where | ATT&CK |
|---|---|---|
| Logging disabled/deleted (CloudTrail `StopLogging`/`DeleteTrail`, GCP sink/bucket deletion) | CloudTrail, GCP | T1562.008 |
| Console login failures then success, new region/IP, no MFA | CloudTrail, Entra/Graph, O365 | T1110, T1078.004 |
| New access keys / service accounts / role trust changes | CloudTrail, GCP | T1098.001, T1136.003 |
| Mass object deletion (rule 80252) or bucket policy made public | CloudTrail | T1485, T1530 |
| Mailbox forwarding rules, suspicious downloads (rule 91724) | Office 365 | T1114.003, T1530 |
| Secrets removed/rotated unexpectedly, secret-scanning hits | GitHub | T1552 |
| Shell in container (rule 87908), host file copied in (rule 87910), privileged container | Docker | T1609, T1611 |

## Containment is outside Wazuh active response

Wazuh AR acts on endpoints with agents; it cannot disable an IAM user, revoke a cloud session or delete
a GitHub token. Record cloud containment as **manual recommendations** in the finding (disable access
key, revoke sessions, restore logging, rotate secret) with the exact identity and resource. Only
host-level actions for a compromised VM or container host with a Wazuh agent go to response-planner.

## Output

- `add_entities`: cloud identity (type `user`, value = ARN / UPN / principal), source IP, resource
  names (type `host` or `url` as appropriate), repository.
- `link_mitre` for the pattern (cloud sub-techniques where they apply).
- `add_finding`: source integration, identity, what happened, baseline comparison, verdict, and manual
  cloud containment steps.
