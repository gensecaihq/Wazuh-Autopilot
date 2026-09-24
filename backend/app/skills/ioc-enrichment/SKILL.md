---
name: ioc-enrichment
description: Enrich indicators (IPs, domains, URLs, hashes) with reputation and context, grade source reliability with the Admiralty Code, and respect TLP and data-egress rules; use when a case contains external indicators.
allowed-tools: get_case check_ioc_reputation analyze_security_threat search_external_context search_security_events add_entities add_finding update_case
metadata:
  category: intel
  display_name: IOC Enrichment
  standards: [nist-csf-2, mitre-attack, nist-800-61r3]
  version: "1.1"
---
# IOC Enrichment

Turn raw indicators into decisions: block, watch, or ignore. NIST CSF 2.0 ID.RA
(threat intelligence informs risk) and DE.AE (context for adverse events).

## Procedure

1. `get_case` — list indicators with role `attacker` or `observed` that are **public**:
   public IPs, internet domains, URLs, file hashes.
2. For each (max 20 per run, attacker-role first):
   - `check_ioc_reputation(indicator=...)` — reputation verdict and sources.
   - `analyze_security_threat(indicator=..., indicator_type=...)` — threat context.
   - `search_security_events(query=<indicator>, srcip=<ip>, time_range="7d")` — internal
     sightings (how many hosts?). For hashes, check whether the Wazuh VirusTotal
     integration already scored the file: rule 87105 (level 12) means positives were
     found; rule 87104 means none; rules 87101, 87102 are integration errors (rate limit,
     credentials), not verdicts. `get_wazuh_alerts(rule_groups=["virustotal"])` lists them.
     Load `wazuh-malware-detection` for detail.
3. Optionally `search_external_context` for public reporting — see egress rules.
4. Grade each source with the Admiralty Code; combine into a verdict.

## Egress rules for search_external_context

`search_external_context` sends the query **outside the environment** (third-party web
search). Only send:
- Public IPs, public domains/URLs, file hashes, CVE ids, malware/actor names.

Never send: internal hostnames, internal IPs (RFC 1918 etc.), usernames, email addresses,
case ids, customer names, file paths, or raw log lines. If unsure, don't send.
Respect TLP: indicators received as TLP:RED or TLP:AMBER+STRICT must not be queried
externally.

## Admiralty Code (NATO / STANAG 2511)

Source reliability: **A** completely reliable · **B** usually reliable · **C** fairly reliable
· **D** not usually reliable · **E** unreliable · **F** cannot be judged.
Information credibility: **1** confirmed by other sources · **2** probably true · **3**
possibly true · **4** doubtful · **5** improbable · **6** cannot be judged.

Typical grading: commercial/curated feed with history → B; single open-source blocklist →
C; one-off paste or forum post → D/F. Internal Wazuh sightings of confirmed attacks → A1.

## Pyramid of Pain (value of blocking)

Hash values (trivial for attacker to change) < IP addresses < Domain names < Network/host
artifacts < Tools < TTPs (hardest to change). Prefer recommending detections on
artifacts/TTPs; treat IP blocks as short-lived (24h–7d).

## Verdict per indicator

| Verdict | Criteria | Recommendation |
|---|---|---|
| malicious | ≥ 1 reliable (A/B) source rates malicious, or confirmed internal attack | block (time-bound), hunt for other sightings |
| suspicious | only C/D sources, or behaviour-only | watch; include in detection review |
| benign | known CDN / cloud provider / business partner with clean history | do not block; note shared-infrastructure risk |
| unknown | no data | rely on behavioural evidence |

Shared infrastructure warning: cloud/CDN IPs (large providers) host many tenants —
blocking them can cause outages; state this explicitly.

## Output

- `add_entities` updating each indicator's `enrichment`: verdict, sources with Admiralty
  grade, first/last seen internally, internal host count, TLP.
- `add_finding` titled `IOC enrichment` with the per-indicator table and recommendation.
  standard_refs: `NIST-CSF-2:ID.RA`, `NIST-CSF-2:DE.AE`.
- `update_case` confidence if intelligence materially changes it.
