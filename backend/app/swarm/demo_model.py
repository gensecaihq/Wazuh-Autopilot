"""Deterministic scripted model for demos, CI and air-gapped evaluation.

It implements the Strands Model interface and drives each agent through a
realistic, role-specific sequence of real tool calls (skills, Wazuh MCP,
platform tools, swarm handoffs). Tool results feed back into later steps, so
cases, findings, entities and action proposals are created for real. It does
not reason: it is a stand-in so the platform can be exercised end to end
without an LLM.
"""

import asyncio
import ipaddress
import json
import random
import re
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from strands.models.model import Model

SUSPICIOUS_PROCS = ("xmrig", "kworkerd", "kdevtmpfsi", "minerd", "rundll32", "powershell", "nc", "ncat", "socat", "mimikatz")
LEVEL_SEVERITY = [(15, "critical"), (12, "high"), (8, "medium"), (5, "low"), (0, "informational")]


def _public_ips(text: str) -> list[str]:
    out = []
    for m in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
        try:
            ip = ipaddress.ip_address(m)
        except ValueError:
            continue
        if ip.is_global and m not in out:
            out.append(m)
    return out


def _first(pattern: str, text: str, group: int = 1, last: bool = False) -> str | None:
    matches = list(re.finditer(pattern, text))
    if not matches:
        return None
    return (matches[-1] if last else matches[0]).group(group)


class _Ctx:
    def __init__(self, text: str, handoff_msg: str):
        self.text = text
        self.case = (_first(r'"case_id"\s*:\s*"(INC-\d{4,})"', text, last=True)
                     or _first(r"\b(INC-\d{4,})\b", text, last=True))
        ips = _public_ips(text)
        self.src_ip = _first(r'"srcip"\s*:\s*"([0-9.]+)"', text) or (ips[0] if ips else None)
        self.agent_id = (_first(r'"agent"\s*:\s*\{[^}]*?"id"\s*:\s*"(\d{3,})"', text)
                         or _first(r'"agent_id"\s*:\s*"(\d{3,})"', text))
        self.agent_name = (_first(r'"agent"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]+)"', text)
                           or _first(r'"agent_name"\s*:\s*"([^"]+)"', text))
        self.rule_desc = _first(r'"description"\s*:\s*"([^"]{5,160})"', text)
        self.rule_id = _first(r'"rule"\s*:\s*\{[^}]*?"id"\s*:\s*"(\d+)"', text)
        lvl = _first(r'"level"\s*:\s*(\d+)', text)
        self.level = int(lvl) if lvl else 10
        self.user = _first(r'"dstuser"\s*:\s*"([^"]+)"', text)
        self.mitre = sorted(set(re.findall(r"\bT\d{4}(?:\.\d{3})?\b", text)))
        self.injection = bool(re.search(r"(?i)ignore (all |previous |prior )?instructions|disregard .*instructions|you are now", text))
        self.handoff_msg = handoff_msg
        self.proc = None
        for m in re.finditer(r'\{[^{}]*"(?:name|cmd|command)"\s*:\s*"([^"]+)"[^{}]*\}', text):
            blob, name = m.group(0), m.group(1)
            if any(s in name.lower() for s in SUSPICIOUS_PROCS):
                pid = _first(r'"(?:pid|process_id)"\s*:\s*"?(\d+)', blob)
                self.proc = {"name": name, "pid": pid}
                break
        self.kev = sorted(set(re.findall(r"CVE-\d{4}-\d{4,7}", text)))[:5]
        self.action_type = _first(r'"type"\s*:\s*"(block_ip|firewall_drop|host_deny|isolate_host|kill_process|disable_user|quarantine_file)"', text)
        self.action_target = _first(r'"target"\s*:\s*"([^"]+)"', text)

    @property
    def severity(self) -> str:
        return next(s for lvl, s in LEVEL_SEVERITY if self.level >= lvl)

    @property
    def host(self) -> str:
        return self.agent_name or (f"agent {self.agent_id}" if self.agent_id else "the affected host")


def _T(name, **inp):
    return ("tool", name, inp)


def _H(target, message):
    return ("tool", "handoff_to_agent", {"agent_name": target, "message": message, "context": {}})


def _say(text):
    return ("text", text)


def _script(agent: str, c: _Ctx) -> list:
    case = c.case or ""
    ip = c.src_ip or "203.0.113.50"
    title = f"{(c.rule_desc or 'Suspicious activity').rstrip('.')} on {c.host}" + (f" from {ip}" if c.src_ip else "")
    if agent == "triage":
        entities = [{"type": "host", "value": c.agent_name or c.host, "role": "victim", "enrichment": {"agent_id": c.agent_id}}]
        if c.src_ip:
            entities.append({"type": "ip", "value": ip, "role": "attacker"})
        if c.user:
            entities.append({"type": "user", "value": c.user, "role": "victim"})
        steps = [
            _T("skills", skill_name="alert-triage"),
            _T("search_cases", query=ip if c.src_ip else (c.agent_name or "")),
            _T("get_wazuh_alerts", limit=20, agent_id=c.agent_id or "", level="5+", timestamp_start="now-6h"),
            _T("create_case", title=title[:200], severity=c.severity,
               summary=f"Wazuh rule {c.rule_id or '?'} (level {c.level}) fired on {c.host}. "
                       + (f"Source {ip} is external. " if c.src_ip else "")
                       + "Opened for correlation and investigation.",
               confidence=0.72 if c.level >= 10 else 0.55),
            ("case_tool", "add_entities", {"entities": entities}),
            ("case_tool", "update_case", {"status": "triage", "summary":
                f"Wazuh rule {c.rule_id or '?'} (level {c.level}) on {c.host}"
                + (f" from external source {ip}" if c.src_ip else "")
                + f". Triaged as {c.severity}; handed to correlation for scoping."}),
        ]
        if c.injection:
            steps.append(("case_tool", "add_finding", {
                "title": "Prompt-injection attempt embedded in alert data",
                "body_md": "Alert fields contain text addressed to an AI analyst (e.g. 'ignore previous instructions'). "
                           "Treated as attacker-controlled data and ignored; the attempt itself is an indicator of a "
                           "targeted attack against automated triage.",
                "standard_refs": ["OWASP-LLM01"], "confidence": 0.9}))
        steps.append(_H("correlation", f"{{case}} opened for {title}. Severity {c.severity}. Correlate activity for "
                                       f"{ip if c.src_ip else c.host} over the last 24h and map to ATT&CK."))
        steps.append(_say(f"Triage complete: {{case}} ({c.severity}). Handed to correlation."))
        return steps
    if agent == "correlation":
        techniques = [{"technique_id": t, "name": "", "tactic": "", "confidence": 0.7,
                       "evidence": f"Wazuh rule {c.rule_id} mapping"} for t in (c.mitre or ["T1110"])[:3]]
        return [
            _T("skills", skill_name="alert-correlation"),
            _T("search_security_events", query=ip if c.src_ip else (c.agent_name or "*"), time_range="24h", limit=50),
            _T("analyze_alert_patterns", time_range="24h"),
            ("case_tool", "link_mitre", {"techniques": techniques}),
            ("case_tool", "add_finding", {
                "title": f"Activity from {ip} correlated across the estate" if c.src_ip else f"Correlated activity on {c.host}",
                "body_md": f"- Pivoted on {'source ' + ip if c.src_ip else c.host} across 24h of Wazuh events.\n"
                           f"- Pattern is consistent with {', '.join(t['technique_id'] for t in techniques)}.\n"
                           "- Escalating to Tier 3 for host-level investigation.",
                "standard_refs": ["NIST-CSF-2:DE.AE", "MITRE-ATTACK:" + techniques[0]["technique_id"]], "confidence": 0.75}),
            ("case_tool", "update_case", {"status": "investigating"}),
            _H("investigation", "{case}: correlation confirms repeated activity. Investigate the host for compromise "
                                "(processes, listening ports, persistence) and scope the blast radius."),
            _say("Correlation done; {case} escalated to investigation."),
        ]
    if agent == "investigation":
        return [
            _T("skills", skill_name="host-forensics"),
            _T("get_agent_processes", agent_id=c.agent_id or "001"),
            _T("get_agent_ports", agent_id=c.agent_id or "001"),
            ("case_tool", "add_finding", {
                "title": f"Host review of {c.host}",
                "body_md": ("Reviewed running processes and listening ports via Wazuh syscollector.\n\n"
                            + (f"- **Suspicious process:** `{c.proc['name']}` (pid {c.proc['pid']}).\n" if c.proc else
                               "- No clearly malicious processes in the current snapshot.\n")
                            + "- Evidence preserved in the case timeline (NIST SP 800-61r3 evidence handling)."),
                "standard_refs": ["NIST-800-61r3:Respond", "ISO-27001:A.5.28"], "confidence": 0.7}),
            _H("threat-intel", f"{{case}}: host reviewed. Enrich {ip} and any indicators; tell the IR lead how "
                               "confident we are that this is malicious."),
            _say("Investigation recorded on {case}; indicators passed to CTI."),
        ]
    if agent == "threat-intel":
        return [
            _T("skills", skill_name="ioc-enrichment"),
            _T("check_ioc_reputation", indicator=ip, indicator_type="ip"),
            ("case_tool", "add_finding", {
                "title": f"Indicator enrichment for {ip}",
                "body_md": f"`{ip}` checked against reputation sources. Source reliability graded B2 (Admiralty). "
                           "Assessment: **likely** malicious infrastructure (ICD 203 estimative language).",
                "standard_refs": ["MITRE-ATTACK:TA0001"], "confidence": 0.8}),
            _H("response-planner", f"{{case}}: {ip} assessed likely malicious (B2). Plan proportionate containment."),
            _say("Enrichment complete for {case}; handed to the IR lead."),
        ]
    if agent == "response-planner":
        steps = [_T("skills", skill_name="response-planning")]
        if c.src_ip:
            steps.append(("case_tool", "propose_action", {
                "type": "block_ip", "target": ip,
                "params": {"ip_address": ip, **({"agent_id": c.agent_id} if c.agent_id else {})},
                "confidence": 0.9 if c.level >= 10 else 0.7,
                "rationale": f"Contain external source {ip} (D3-ITF inbound traffic filtering). Low risk and reversible "
                             "with wazuh_firewall_allow. Evidence already preserved."}))
        if c.proc and c.proc.get("pid") and c.agent_id:
            steps.append(("case_tool", "propose_action", {
                "type": "kill_process", "target": c.proc["pid"],
                "params": {"agent_id": c.agent_id, "process_id": c.proc["pid"]}, "confidence": 0.86,
                "rationale": f"Terminate suspicious process {c.proc['name']} (D3-PT) after evidence capture."}))
        steps += [
            ("case_tool", "add_finding", {
                "title": "Containment plan",
                "body_md": "1. Contain: network block of the external source (reversible).\n"
                           "2. Eradicate: remove malicious process/persistence if confirmed.\n"
                           "3. Recover: monitor for recurrence for 24h; close when quiet.\n\n"
                           "Ordering follows SANS PICERL: evidence before eradication, containment before eradication.",
                "standard_refs": ["NIST-800-61r3:Respond", "SANS-PICERL:Containment"], "confidence": 0.85}),
            ("case_tool", "update_case", {"status": "contained" if c.src_ip else "investigating"}),
            _say("Response plan for {case} submitted under the autonomy policy."),
        ]
        return steps
    if agent == "responder":
        check = {"block_ip": "wazuh_check_blocked_ip", "firewall_drop": "wazuh_check_blocked_ip",
                 "host_deny": "wazuh_check_blocked_ip", "isolate_host": "wazuh_check_agent_isolation",
                 "kill_process": "wazuh_check_process", "disable_user": "wazuh_check_user_status",
                 "quarantine_file": "wazuh_check_file_quarantine"}.get(c.action_type or "block_ip")
        args = {"ip_address": c.action_target or ip} if "blocked_ip" in (check or "") else {"agent_id": c.agent_id or "001"}
        if check == "wazuh_check_process":
            args["process_id"] = c.action_target or "0"
        return [
            _T("skills", skill_name="action-verification"),
            _T(check, **args),
            ("case_tool", "add_finding", {
                "title": f"Verification of {c.action_type or 'action'} on {c.action_target or ip}",
                "body_md": f"Checked the endpoint with `{check}` rather than trusting the dispatch status. "
                           "Result recorded above; no rollback recommended.",
                "standard_refs": ["MITRE-D3FEND"], "confidence": 0.8}),
            _say("Verification recorded."),
        ]
    if agent == "threat-hunter":
        return [
            _T("skills", skill_name="threat-hunting"),
            _T("search_security_events", query="authentication_success AND srcip:!10.0.0.0/8", time_range="7d", limit=100),
            _T("analyze_alert_patterns", time_range="7d"),
            _T("save_report", kind="hunt", title="Hunt: successful external authentications after failures (T1110 → T1078)",
               body_md="**Hypothesis:** an external actor succeeded after password guessing.\n\n**Data:** Wazuh auth events, 7d.\n\n"
                       "**Result:** patterns reviewed; candidate detection handed to detection engineering.\n"),
            _say("Hunt complete; results saved and a detection idea passed on."),
        ]
    if agent == "detection-engineer":
        return [
            _T("skills", skill_name="detection-engineering"),
            _T("get_wazuh_rules_summary"),
            _T("propose_detection", title="Successful SSH login after brute force from same source",
               rule_format="sigma",
               rule_body="title: SSH success after brute force\nstatus: experimental\nlogsource:\n  product: linux\n  service: sshd\n"
                         "detection:\n  failures:\n    rule.id: ['5710','5712']\n  success:\n    rule.id: '5715'\n"
                         "  timeframe: 30m\n  condition: failures | count() by data.srcip > 10 and success\nlevel: high\n",
               rationale="ADS: detect T1110 → T1078 transition. Backtest against 30d of alerts before enabling.",
               mitre=["T1110.001", "T1078"]),
            _say("Detection proposal submitted for human review."),
        ]
    if agent == "vuln-management":
        return [
            _T("skills", skill_name="vulnerability-prioritization"),
            _T("get_wazuh_critical_vulnerabilities", limit=50),
            _T("get_wazuh_vulnerability_summary"),
            _T("save_report", kind="vulnerability", title="Vulnerability priorities (KEV → EPSS → CVSS)",
               body_md="| Priority | CVE | SSVC | SLA |\n|---|---|---|---|\n"
                       + "\n".join(f"| {i+1} | {cve} | {'Act' if i < 2 else 'Attend'} | {'48h' if i < 2 else '14d'} |"
                                   for i, cve in enumerate(c.kev or ["CVE-2024-3400", "CVE-2023-4966"]))
                       + "\n\nKEV-listed CVEs ranked first per CISA BOD 22-01 guidance."),
            _say("Vulnerability priorities saved (KEV first)."),
        ]
    if agent == "compliance":
        return [
            _T("skills", skill_name="compliance-mapping"),
            _T("run_compliance_check", framework="PCI-DSS"),
            _T("get_iso27001_gap_analysis"),
            _T("save_report", kind="compliance", title="Compliance posture: PCI DSS v4.0.1 and ISO 27001:2022",
               body_md="Checks executed via Wazuh SCA and compliance tools. Gaps mapped to PCI DSS Req 10/11 and "
                       "ISO 27001 A.8.8/A.8.16 with evidence statements for audit."),
            _say("Compliance report saved."),
        ]
    if agent == "reporting":
        return [
            _T("skills", skill_name="executive-reporting"),
            _T("get_wazuh_alert_summary", time_range="24h"),
            _T("save_report", kind="executive" if not case else "incident",
               title=f"Incident summary {case}" if case else "Daily SOC briefing",
               body_md="**Bottom line:** activity contained under policy; no business impact observed.\n\n"
                       "**What happened / what we did / what's next** are recorded in the case timeline."),
            _say("Report saved."),
        ]
    if agent == "platform-engineer":
        return [
            _T("skills", skill_name="wazuh-platform-health"),
            _T("get_wazuh_running_agents"),
            _T("get_wazuh_agents", status="disconnected"),
            _T("get_wazuh_remoted_stats"),
            _T("get_wazuh_manager_error_logs", limit=50),
            _T("add_finding", case_id="", title="Wazuh platform health check",
               body_md="- Agent connectivity reviewed; disconnected or never-connected agents are detection blind spots.\n"
                       "- Manager error log and remoted stats checked for dropped events and queue flooding "
                       "(rule 203, level 9, means an agent event queue is full and events may be lost).",
               standard_refs=["NIST-CSF-2:DE.CM", "CIS-v8.1:8"], confidence=0.8),
            _T("save_report", kind="shift", title="Wazuh platform health",
               body_md="**Fleet:** connectivity reviewed. **Manager:** error log reviewed. **Ingestion:** remoted stats reviewed. "
                       "Follow up on any disconnected agents or dropped events."),
            _say("Platform health check complete."),
        ]
    if agent == "commander":
        return [
            _T("skills", skill_name="swarm-coordination"),
            _T("get_wazuh_alert_summary", time_range="24h"),
            _T("get_top_security_threats", time_range="24h"),
            _H("threat-hunter", "Top threats reviewed. Hunt for successful authentications following brute force in the last 7 days."),
            _say("Dispatched the hunt team."),
        ]
    return [_say("Acknowledged.")]


class DemoModel(Model):
    def __init__(self, model_id: str = "autopilot-demo-1", latency: tuple[float, float] = (0.35, 1.1)):
        self.config = {"model_id": model_id}
        self.latency = latency

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs) -> AsyncGenerator[dict, None]:
        raise NotImplementedError("the demo model does not support structured output")
        yield {}  # pragma: no cover

    @staticmethod
    def _flatten(messages) -> tuple[str, int, str]:
        """(all text, tool uses since the last real user turn, last user text)."""
        texts, since_user, last_user = [], 0, ""
        skill_calls = {b["toolUse"].get("toolUseId") for m in messages for b in m.get("content", [])
                       if "toolUse" in b and b["toolUse"].get("name") == "skills"}
        for m in messages:
            real_user = m.get("role") == "user" and any("text" in b for b in m.get("content", []))
            if real_user:
                since_user = 0
            for b in m.get("content", []):
                if "text" in b:
                    texts.append(b["text"])
                    if m.get("role") == "user":
                        last_user = b["text"]
                if "toolUse" in b:
                    since_user += 1
                    texts.append(json.dumps(b["toolUse"].get("input", {})))
                if "toolResult" in b:
                    if b["toolResult"].get("toolUseId") in skill_calls:
                        continue  # skill instructions contain example values; don't mine them
                    for rb in b["toolResult"].get("content", []):
                        if "text" in rb:
                            texts.append(rb["text"])
                        elif "json" in rb:
                            texts.append(json.dumps(rb["json"]))
        return "\n".join(texts), since_user, last_user

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[dict]:
        agent = _first(r"\[agent:([a-z0-9-]+)\]", system_prompt or "") or "agent"
        available = {s["name"] for s in tool_specs or []}
        text, step, last_user = self._flatten(messages)
        ctx = _Ctx(text, last_user)
        plan = []
        for s in _script(agent, ctx):
            if s[0] in {"tool", "case_tool"} and s[1] not in available:
                continue
            plan.append(s)
        if not plan or plan[-1][0] != "text":
            plan.append(_say("Done."))
        current = plan[min(step, len(plan) - 1)]
        await asyncio.sleep(random.uniform(*self.latency))
        in_tokens = (len(system_prompt or "") + len(text)) // 4
        yield {"messageStart": {"role": "assistant"}}
        if current[0] == "text":
            out = current[1].replace("{case}", ctx.case or "the case")
            for i in range(0, len(out), 48):
                yield {"contentBlockDelta": {"delta": {"text": out[i:i + 48]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            out_tokens = len(out) // 4 + 20
        else:
            name, inp = current[1], dict(current[2])
            if current[0] == "case_tool":
                inp = {"case_id": ctx.case or "", **inp}
            if name == "handoff_to_agent":
                inp["message"] = inp["message"].replace("{case}", ctx.case or "the case")
                inp["context"] = {"case_id": ctx.case}
            thought = f"Next: {name.replace('_', ' ')}."
            yield {"contentBlockDelta": {"delta": {"text": thought}}}
            yield {"contentBlockStop": {}}
            payload = json.dumps(inp)
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"demo-{random.getrandbits(40):x}", "name": name}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": payload}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            out_tokens = len(payload) // 4 + 30
        yield {"metadata": {"usage": {"inputTokens": in_tokens, "outputTokens": out_tokens,
                                      "totalTokens": in_tokens + out_tokens},
                            "metrics": {"latencyMs": int(self.latency[1] * 1000)}}}
