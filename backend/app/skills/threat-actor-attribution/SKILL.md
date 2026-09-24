---
name: threat-actor-attribution
description: Assess possible threat-actor or campaign links using the Diamond Model and ATT&CK group data, expressed with calibrated estimative language; use only when a case shows enough TTP or infrastructure overlap to justify attribution discussion.
allowed-tools: get_case analyze_security_threat check_ioc_reputation search_external_context get_top_security_threats add_finding
metadata:
  category: intel
  display_name: Threat Actor Attribution
  standards: [mitre-attack, nist-csf-2]
  version: "1.0"
---
# Threat Actor Attribution

Attribution is rarely needed to respond, and wrong attribution causes real harm
(misdirected response, bad executive decisions). Do it carefully or not at all.

## When to attempt

Attempt only if at least two of these hold:
- Infrastructure (IP/domain) with a reliable (A/B) public link to a named cluster.
- Tooling or malware family with known actor associations.
- A distinctive TTP sequence matching an ATT&CK group profile.
- Targeting consistent with the actor's known sector/geography interest.

Otherwise record "attribution not assessed — insufficient evidence" and stop.

## Diamond Model

Describe the intrusion on four vertices and the links between them:

| Vertex | Questions | Evidence sources |
|---|---|---|
| Adversary | Who operates it? (often unknown — that's fine) | intel reporting |
| Capability | Tools, malware, exploits, techniques | host forensics, ATT&CK mapping |
| Infrastructure | IPs, domains, C2, hosting | IOC enrichment |
| Victim | Which assets, users, sector | case entities, org context |

Meta-features: timestamp, phase (ATT&CK tactic), result, direction, methodology.
Pivot vertex-to-vertex (e.g. infrastructure → other victims seen in intel) to test links.

## Comparing to ATT&CK groups

1. List the case's confirmed techniques (from `mitre-attack-mapping`).
2. Compare with candidate groups' technique sets from public ATT&CK group pages
   (via `search_external_context` for the group name — public data only).
3. Overlap on common techniques (T1059, T1078, T1110) means little; weight distinctive
   techniques and tool names higher.
4. Record competing hypotheses, including "unknown / commodity actor".

## Estimative language (ICD 203 style)

Use consistent probability terms and state confidence separately:

| Term | Approx. probability |
|---|---|
| almost no chance / remote | 1–5% |
| very unlikely | 5–20% |
| unlikely | 20–45% |
| roughly even chance | 45–55% |
| likely | 55–80% |
| very likely | 80–95% |
| almost certainly | 95–99% |

Confidence (low / moderate / high) reflects evidence quality and source reliability, not
probability. Example: "We assess it is *unlikely* (moderate confidence) that this activity
is linked to group X; infrastructure overlap is limited to a shared hosting provider."

## Rules

- Never name a nation-state sponsor on your own; at most reference public reporting and
  grade it.
- Distinguish commodity crimeware, opportunistic scanning, and targeted operations.
- Attribution never changes containment urgency by itself.

## Output

- `add_finding` titled `Attribution assessment` with the Diamond Model table, competing
  hypotheses with estimative language and confidence, sources with Admiralty grades,
  and key gaps. standard_refs: `MITRE-ATTACK`.
