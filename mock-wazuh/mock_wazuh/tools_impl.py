"""Tool implementations for the mock Wazuh MCP server.

Each handler takes (env, args) and returns a JSON-serialisable result; the
server wraps it as "<Label>:\n<json>" text content, exactly like
gensecaihq/Wazuh-MCP-Server does.
"""

from __future__ import annotations

import collections
import hashlib
import ipaddress
import re
import time

from .sim import (AGENTS, AGENTS_BY_ID, ATTACKERS, KEV_CVES, THREAT_INTEL, WAZUH_VERSION, Environment, iso,
                  parse_time, since_range, strip_private)


class ToolError(Exception):
    pass


WRITE_TOOLS = {
    "wazuh_block_ip", "wazuh_isolate_host", "wazuh_kill_process", "wazuh_disable_user", "wazuh_quarantine_file",
    "wazuh_active_response", "wazuh_firewall_drop", "wazuh_host_deny", "wazuh_restart", "wazuh_unisolate_host",
    "wazuh_enable_user", "wazuh_restore_file", "wazuh_firewall_allow", "wazuh_host_allow",
}
REVERSAL_TOOLS = {"wazuh_unisolate_host", "wazuh_enable_user", "wazuh_restore_file", "wazuh_firewall_allow", "wazuh_host_allow"}
OPEN_WORLD_TOOLS = {"search_external_context"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _limit(args, default=100, max_val=1000):
    v = args.get("limit", default)
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise ToolError(f"limit: must be an integer, got {v!r}")
    if v < 1 or v > max_val:
        raise ToolError(f"limit: must be between 1 and {max_val}")
    return v


def _agent(args, required=False, key="agent_id"):
    aid = args.get(key)
    if aid in (None, ""):
        if required:
            raise ToolError(f"{key}: required")
        return None
    aid = str(aid).strip()
    if aid.isdigit():
        aid = aid.zfill(3)
    if aid not in AGENTS_BY_ID:
        raise ToolError(f"{key}: agent '{aid}' not found")
    return aid


def _bool(args, key, default):
    v = args.get(key, default)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _level_filter(level):
    if level in (None, ""):
        return None
    s = str(level).strip()
    if not re.match(r"^[0-9]{1,2}\+?$", s):
        raise ToolError(f"level: invalid format '{s}'. Use a number 0-15, optionally with '+' (e.g., '12', '10+')")
    return int(s.rstrip("+"))


def _ip(value, key="ip_address"):
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        raise ToolError(f"{key}: '{value}' is not a valid IP address")


def _wazuh_list(items, total=None, message="All selected items were returned"):
    return {"data": {"affected_items": items, "total_affected_items": len(items) if total is None else total,
                     "total_failed_items": 0, "failed_items": []}, "message": message, "error": 0}


def _truncation(result, limit):
    d = result["data"]
    if len(d["affected_items"]) >= limit and d["total_affected_items"] > limit:
        d["warning"] = (f"Results truncated: showing {limit} of {d['total_affected_items']} matching items. "
                        "Narrow the time range or add filters to see the rest.")
    return result


def compact_alert(a):
    c = {"timestamp": a["timestamp"], "agent": {"id": a["agent"]["id"], "name": a["agent"]["name"]},
         "rule": {"id": a["rule"]["id"], "level": a["rule"]["level"], "description": a["rule"]["description"], "groups": a["rule"]["groups"]}}
    if a["rule"].get("mitre"):
        c["rule"]["mitre"] = a["rule"]["mitre"]
    d = a.get("data") or {}
    if d.get("srcip"):
        c["srcip"] = d["srcip"]
    if d.get("dstip"):
        c["dstip"] = d["dstip"]
    if a.get("syscheck"):
        c["syscheck"] = {"path": a["syscheck"].get("path", ""), "event": a["syscheck"].get("event", "")}
    if a.get("full_log"):
        log = str(a["full_log"])
        c["full_log"] = log[:300] + ("..." if len(log) > 300 else "")
    c["id"] = a["id"]
    return c


def _filter_alerts(env: Environment, args, since_default=None):
    level = _level_filter(args.get("level"))
    rule_id = args.get("rule_id")
    agent_id = _agent(args)
    groups = args.get("rule_groups") or []
    if isinstance(groups, str):
        groups = [groups]
    try:
        start = parse_time(args.get("timestamp_start"), since_default)
        end = parse_time(args.get("timestamp_end"), None)
    except ValueError as e:
        raise ToolError(str(e))
    srcip = args.get("srcip")
    dstip = args.get("dstip")
    out = []
    for a in reversed(env.snapshot()):  # newest first
        ts = a["_ts"]
        if start and ts < start:
            break
        if end and ts > end:
            continue
        r = a["rule"]
        if level is not None and r["level"] < level:
            continue
        if rule_id and str(rule_id) != r["id"]:
            continue
        if agent_id and a["agent"]["id"] != agent_id:
            continue
        if groups and not set(groups) & set(r["groups"]):
            continue
        d = a.get("data") or {}
        if srcip and d.get("srcip") != srcip:
            continue
        if dstip and d.get("dstip") != dstip:
            continue
        out.append(a)
    return out


def _alert_result(alerts, limit, compact):
    items = [compact_alert(a) if compact else strip_private(a) for a in alerts[:limit]]
    return _truncation(_wazuh_list(items, total=len(alerts)), limit)


def _time_range(args, key="time_range", default="24h"):
    r = args.get(key) or default
    if r not in ("1h", "6h", "12h", "1d", "24h", "7d", "30d"):
        raise ToolError(f"{key}: invalid value '{r}'")
    return r


# ---------------------------------------------------------------------------
# alerts
# ---------------------------------------------------------------------------
def get_wazuh_alerts(env, args):
    limit = _limit(args, 100, 1000)
    return _alert_result(_filter_alerts(env, args), limit, _bool(args, "compact", True))


def get_wazuh_alert_summary(env, args):
    r = _time_range(args)
    group_by = args.get("group_by") or "rule.level"
    alerts = _filter_alerts(env, {}, since_range(r))
    key = {
        "rule.level": lambda a: str(a["rule"]["level"]),
        "rule.id": lambda a: f'{a["rule"]["id"]} - {a["rule"]["description"]}',
        "agent.id": lambda a: a["agent"]["id"],
        "agent.name": lambda a: a["agent"]["name"],
    }.get(group_by)
    c = collections.Counter()
    if group_by == "rule.groups":
        for a in alerts:
            c.update(a["rule"]["groups"])
    else:
        c.update(key(a) for a in alerts)
    buckets = [{"key": k, "doc_count": v} for k, v in c.most_common(50)]
    sev = collections.Counter()
    for a in alerts:
        lv = a["rule"]["level"]
        sev["critical" if lv >= 12 else "high" if lv >= 10 else "medium" if lv >= 7 else "low"] += 1
    return {"time_range": r, "group_by": group_by, "total_alerts": len(alerts), "buckets": buckets, "severity_distribution": dict(sev)}


def analyze_alert_patterns(env, args):
    r = _time_range(args)
    min_freq = int(args.get("min_frequency") or 5)
    alerts = _filter_alerts(env, {}, since_range(r))
    by_rule = collections.defaultdict(list)
    for a in alerts:
        by_rule[a["rule"]["id"]].append(a)
    patterns = []
    for rid, items in by_rule.items():
        if len(items) < min_freq:
            continue
        srcs = collections.Counter((i.get("data") or {}).get("srcip") for i in items if (i.get("data") or {}).get("srcip"))
        agents = collections.Counter(i["agent"]["name"] for i in items)
        patterns.append({
            "rule_id": rid, "description": items[0]["rule"]["description"], "level": items[0]["rule"]["level"],
            "count": len(items), "first_seen": items[-1]["timestamp"], "last_seen": items[0]["timestamp"],
            "top_source_ips": [{"ip": k, "count": v} for k, v in srcs.most_common(5)],
            "top_agents": [{"agent": k, "count": v} for k, v in agents.most_common(5)],
            "mitre": items[0]["rule"].get("mitre"),
        })
    patterns.sort(key=lambda p: (p["level"], p["count"]), reverse=True)
    hourly = collections.Counter(a["timestamp"][11:13] for a in alerts)
    anomalies = [p for p in patterns if p["level"] >= 10]
    return {"time_range": r, "total_alerts": len(alerts), "patterns": patterns[:30],
            "hourly_distribution": dict(sorted(hourly.items())),
            "high_severity_patterns": len(anomalies),
            "summary": f"{len(patterns)} recurring patterns (>= {min_freq} occurrences); {len(anomalies)} at level 10+."}


def get_alerts_aggregated(env, args):
    try:
        start = parse_time(args.get("timestamp_start"), since_range("24h"))
    except ValueError as e:
        raise ToolError(str(e))
    alerts = _filter_alerts(env, {"timestamp_start": args.get("timestamp_start"), "timestamp_end": args.get("timestamp_end")}, start)
    top_rules = int(args.get("top_rules") or 10)
    top_agents = int(args.get("top_agents") or 10)
    rules = collections.Counter((a["rule"]["id"], a["rule"]["description"], a["rule"]["level"]) for a in alerts)
    agents = collections.Counter((a["agent"]["id"], a["agent"]["name"]) for a in alerts)
    levels = collections.Counter(a["rule"]["level"] for a in alerts)
    srcs = collections.Counter((a.get("data") or {}).get("srcip") for a in alerts if (a.get("data") or {}).get("srcip"))
    tactics = collections.Counter()
    for a in alerts:
        tactics.update((a["rule"].get("mitre") or {}).get("tactic", []))
    return {
        "total": len(alerts),
        "by_level": [{"level": k, "count": v} for k, v in sorted(levels.items(), reverse=True)],
        "top_rules": [{"rule_id": k[0], "description": k[1], "level": k[2], "count": v} for k, v in rules.most_common(top_rules)],
        "top_agents": [{"agent_id": k[0], "agent_name": k[1], "count": v} for k, v in agents.most_common(top_agents)],
        "top_source_ips": [{"srcip": k, "count": v} for k, v in srcs.most_common(10)],
        "mitre_tactics": [{"tactic": k, "count": v} for k, v in tactics.most_common()],
    }


def search_security_events(env, args):
    q = str(args.get("query") or "").strip()
    if not q:
        raise ToolError("query: required")
    r = _time_range(args)
    limit = _limit(args, 100, 1000)
    base = _filter_alerts(env, {k: args.get(k) for k in ("rule_id", "agent_id", "level", "srcip", "dstip")}, since_range(r))
    terms = [t.lower() for t in q.split() if t not in ("AND", "and")]
    hits = []
    for a in base:
        blob = " ".join([a["rule"]["description"], a.get("full_log", ""), " ".join(a["rule"]["groups"]), a["agent"]["name"],
                         str((a.get("data") or {}).get("srcip", "")), str((a.get("data") or {}).get("dstuser", "")),
                         str((a.get("syscheck") or {}).get("path", ""))]).lower()
        if all(t in blob for t in terms):
            hits.append(a)
    return _alert_result(hits, limit, _bool(args, "compact", True))


# ---------------------------------------------------------------------------
# agents
# ---------------------------------------------------------------------------
def _agent_doc(env, a):
    st = env.agent_state[a["id"]]
    status = st["status"]
    return {
        "id": a["id"], "name": a["name"], "ip": a["ip"], "registerIP": "any" if a["id"] != "000" else "127.0.0.1",
        "status": status, "status_code": 0 if status == "active" else 1,
        "os": {"platform": a["os"][0], "name": a["os"][1], "version": a["os"][2], "arch": "x86_64"},
        "version": f"Wazuh {WAZUH_VERSION}", "manager": "wazuh-manager", "node_name": "master-node",
        "group": a["groups"], "group_config_status": "synced",
        "dateAdd": iso(st["registered"]), "lastKeepAlive": iso(st["last_keepalive"] if status != "active" else time.time() - 12),
        "isolated": a["id"] in env.isolated,
    }


def get_wazuh_agents(env, args):
    aid = _agent(args)
    status = args.get("status")
    limit = _limit(args, 100, 1000)
    items = [_agent_doc(env, a) for a in AGENTS if (not aid or a["id"] == aid) and (not status or env.agent_state[a["id"]]["status"] == status)]
    return _wazuh_list(items[:limit], total=len(items))


def get_wazuh_running_agents(env, args):
    items = [_agent_doc(env, a) for a in AGENTS if env.agent_state[a["id"]]["status"] == "active"]
    return _wazuh_list(items)


def check_agent_health(env, args):
    aid = _agent(args, required=True)
    a = AGENTS_BY_ID[aid]
    doc = _agent_doc(env, a)
    recent = [x for x in _filter_alerts(env, {"agent_id": aid}, since_range("24h"))]
    high = sum(1 for x in recent if x["rule"]["level"] >= 10)
    active = doc["status"] == "active"
    health = "healthy" if active and high < 5 else ("degraded" if active else "unhealthy")
    return {"data": {"agent_id": aid, "name": a["name"], "status": doc["status"], "health_status": health,
                     "last_keepalive": doc["lastKeepAlive"], "version": doc["version"], "os": doc["os"],
                     "sync_status": "synced", "isolated": aid in env.isolated,
                     "alerts_24h": len(recent), "high_severity_alerts_24h": high,
                     "modules": {"syscheck": "running", "rootcheck": "running", "syscollector": "running", "sca": "running", "logcollector": "running"}}}


def get_agent_processes(env, args):
    aid = _agent(args, required=True)
    limit = _limit(args, 100, 1000)
    with env.lock:
        procs = sorted(env.processes[aid].values(), key=lambda p: p["pid"])
    items = [dict(p, agent_id=aid, scan={"time": iso(time.time() - 300)}) for p in procs]
    return _wazuh_list(items[:limit], total=len(items))


def get_agent_ports(env, args):
    aid = _agent(args, required=True)
    limit = _limit(args, 100, 1000)
    with env.lock:
        live_pids = set(env.processes[aid])
        items = [dict(p, agent_id=aid) for p in env.ports[aid] if p["pid"] is None or p["pid"] in live_pids]
    return _wazuh_list(items[:limit], total=len(items))


def get_agent_configuration(env, args):
    aid = _agent(args, required=True)
    a = AGENTS_BY_ID[aid]
    windows = a["os"][0] == "windows"
    dirs = [r"C:\Windows\System32\drivers\etc", r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup", r"C:\Users\*\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"] if windows \
        else ["/etc", "/usr/bin", "/usr/sbin", "/bin", "/sbin", "/boot", "/root/.ssh"]
    return {"data": {"agent_id": aid, "name": a["name"], "configuration": {
        "client": {"server": [{"address": "wazuh-manager", "port": 1514, "protocol": "tcp"}], "notify_time": 10, "time-reconnect": 60},
        "syscheck": {"disabled": "no", "frequency": 43200, "scan_on_start": "yes", "directories": [{"path": d, "realtime": "yes", "check_all": "yes"} for d in dirs]},
        "rootcheck": {"disabled": "no" if not windows else "yes", "frequency": 43200},
        "wodle_syscollector": {"disabled": "no", "interval": "1h", "processes": "yes", "ports": "yes", "packages": "yes"},
        "sca": {"enabled": "yes", "scan_on_start": "yes", "interval": "12h"},
        "active_response": {"disabled": "no", "ca_verification": "yes"},
        "localfile": [{"location": "EventChannel" if windows else "/var/log/auth.log", "log_format": "eventchannel" if windows else "syslog"}],
    }}}


# ---------------------------------------------------------------------------
# vulnerabilities
# ---------------------------------------------------------------------------
def _vuln_items(env, aid=None, severity=None):
    items = []
    for agent_id, vulns in env.vulns.items():
        if aid and agent_id != aid:
            continue
        for v in vulns:
            if severity and v["vulnerability"]["severity"].lower() != severity.lower():
                continue
            items.append(v)
    items.sort(key=lambda v: v["vulnerability"]["score"]["base"], reverse=True)
    return items


def _vuln_out(v, compact):
    if compact:
        return {"cve": v["vulnerability"]["id"], "severity": v["vulnerability"]["severity"], "cvss": v["vulnerability"]["score"]["base"],
                "package": f'{v["package"]["name"]} {v["package"]["version"]}', "agent": v["agent"],
                "detected_at": v["vulnerability"]["detected_at"], "cisa_kev": v["kev"]}
    d = {k: val for k, val in v.items() if not k.startswith("_")}
    return d


def get_wazuh_vulnerabilities(env, args):
    aid = _agent(args)
    sev = args.get("severity")
    limit = _limit(args, 100, 500)
    items = _vuln_items(env, aid, sev)
    return _truncation(_wazuh_list([_vuln_out(v, _bool(args, "compact", True)) for v in items[:limit]], total=len(items)), limit)


def get_wazuh_critical_vulnerabilities(env, args):
    limit = _limit(args, 50, 500)
    items = _vuln_items(env, severity="critical")
    return _truncation(_wazuh_list([_vuln_out(v, _bool(args, "compact", True)) for v in items[:limit]], total=len(items)), limit)


def get_wazuh_vulnerability_summary(env, args):
    tr = args.get("time_range")
    if tr is not None and tr not in ("1d", "7d", "30d"):
        raise ToolError("time_range: Use one of: 1d, 7d, 30d")
    aid = _agent(args)
    items = _vuln_items(env, aid)
    if tr:
        cutoff = time.time() - {"1d": 86400, "7d": 604800, "30d": 2592000}[tr]
        items = [v for v in items if v["_detected_ts"] >= cutoff]
    sev = collections.Counter(v["vulnerability"]["severity"] for v in items)
    by_cve = collections.Counter(v["vulnerability"]["id"] for v in items)
    by_agent = collections.Counter(v["agent"]["name"] for v in items)
    return {"total_vulnerabilities": len(items), "time_range": tr or "all_open",
            "by_severity": {k: sev.get(k, 0) for k in ("Critical", "High", "Medium", "Low")},
            "cisa_kev_count": sum(1 for v in items if v["kev"]),
            "top_cves": [{"cve": k, "affected_agents": c, "cisa_kev": k in KEV_CVES} for k, c in by_cve.most_common(10)],
            "most_vulnerable_agents": [{"agent": k, "count": c} for k, c in by_agent.most_common(10)]}


# ---------------------------------------------------------------------------
# analysis / intel
# ---------------------------------------------------------------------------
def _indicator(args):
    ind = str(args.get("indicator") or "").strip()
    if not ind:
        raise ToolError("indicator: required")
    t = args.get("indicator_type") or "ip"
    if t == "ip":
        _ip(ind, "indicator")
    return ind, t


def _related_alerts(env, ind):
    n = 0
    agents = set()
    last = None
    for a in env.snapshot():
        d = a.get("data") or {}
        if ind in (d.get("srcip"), d.get("dstip"), d.get("hostname")) or ind in str(a.get("full_log", "")):
            n += 1
            agents.add(a["agent"]["name"])
            last = a["timestamp"]
    return n, sorted(agents), last


def check_ioc_reputation(env, args):
    ind, t = _indicator(args)
    n, agents, last = _related_alerts(env, ind)
    ti = THREAT_INTEL.get(ind)
    if ti:
        res = dict(ti)
    elif t == "ip" and ipaddress.ip_address(ind).is_private:
        res = {"reputation": "internal", "risk_score": 0, "tags": ["rfc1918"], "sources": []}
    else:
        h = int(hashlib.sha256(ind.encode()).hexdigest(), 16)
        res = {"reputation": "unknown" if h % 5 else "clean", "risk_score": h % 20, "tags": [], "sources": ["mock-abuse-feed"]}
    geo = ATTACKERS.get(ind)
    return {"indicator": ind, "indicator_type": t, **res,
            "geo": {"country": geo["country"], "city": geo["city"], "asn": geo["asn"], "org": geo["org"]} if geo else None,
            "blocked": ind in env.blocked_ips, "local_sightings": {"alerts": n, "agents": agents, "last_seen": last},
            "note": "Mock threat-intel data for demo purposes."}


def analyze_security_threat(env, args):
    rep = check_ioc_reputation(env, args)
    ind = rep["indicator"]
    alerts = [a for a in env.snapshot() if ind in ((a.get("data") or {}).get("srcip"), (a.get("data") or {}).get("dstip"))]
    techniques = collections.Counter()
    for a in alerts:
        techniques.update((a["rule"].get("mitre") or {}).get("id", []))
    level = "critical" if rep["risk_score"] >= 90 else "high" if rep["risk_score"] >= 70 else "medium" if rep["risk_score"] >= 40 else "low"
    return {"indicator": ind, "indicator_type": rep["indicator_type"], "threat_level": level, "risk_score": rep["risk_score"],
            "reputation": rep["reputation"], "tags": rep["tags"], "local_sightings": rep["local_sightings"],
            "mitre_techniques_observed": [{"technique": k, "count": v} for k, v in techniques.most_common(8)],
            "recommendations": (["Block at perimeter (firewall-drop) on exposed agents", "Hunt for successful authentications from this indicator",
                                 "Review affected hosts for persistence"] if level in ("critical", "high") else ["Monitor"]),
            "blocked": rep["blocked"]}


def search_external_context(env, args):
    q = str(args.get("query") or "").strip()
    if not q:
        raise ToolError("query: required")
    count = int(args.get("count") or 5)
    ti = THREAT_INTEL.get(q)
    results = []
    if ti:
        results.append({"title": f"{q} reported for {', '.join(ti['tags'])}", "url": f"https://intel.example.invalid/indicator/{q}",
                        "snippet": f"Mock community report: {q} associated with {', '.join(ti['tags'])}. Risk score {ti['risk_score']}."})
    results.append({"title": f"Search results for {q}", "url": "https://search.example.invalid/?q=" + q, "snippet": "Mock external context (no data left the box)."})
    return {"query": q, "results": results[:count], "provider": "mock", "note": "The mock server never sends queries off-box."}


def perform_risk_assessment(env, args):
    aid = _agent(args)
    scope = [AGENTS_BY_ID[aid]] if aid else AGENTS
    out = []
    for a in scope:
        alerts = _filter_alerts(env, {"agent_id": a["id"]}, since_range("7d"))
        high = sum(1 for x in alerts if x["rule"]["level"] >= 10)
        crit = sum(1 for x in alerts if x["rule"]["level"] >= 12)
        vulns = env.vulns.get(a["id"], [])
        vcrit = sum(1 for v in vulns if v["vulnerability"]["severity"] == "Critical")
        kev = sum(1 for v in vulns if v["kev"])
        score = min(100, crit * 6 + high * 1.5 + vcrit * 8 + kev * 10 + (15 if a["id"] in ("005", "007") else 0))
        out.append({"agent_id": a["id"], "agent_name": a["name"], "risk_score": round(score, 1),
                    "risk_level": "critical" if score >= 75 else "high" if score >= 50 else "medium" if score >= 25 else "low",
                    "factors": {"critical_alerts_7d": crit, "high_alerts_7d": high, "critical_vulns": vcrit, "kev_vulns": kev,
                                "exposed": "perimeter" in a["groups"] or "web" in a["groups"]}})
    out.sort(key=lambda x: x["risk_score"], reverse=True)
    overall = round(sum(x["risk_score"] for x in out) / max(1, len(out)), 1)
    return {"overall_risk_score": overall if aid is None else out[0]["risk_score"], "assessments": out,
            "recommendations": ["Prioritise CISA KEV vulnerabilities on internet-facing hosts", "Investigate hosts with critical alerts in the last 7 days"]}


def get_top_security_threats(env, args):
    limit = _limit(args, 10, 100)
    r = _time_range(args)
    alerts = [a for a in _filter_alerts(env, {}, since_range(r)) if a["rule"]["level"] >= 7]
    g = collections.defaultdict(list)
    for a in alerts:
        g[a["rule"]["id"]].append(a)
    threats = []
    for rid, items in g.items():
        r0 = items[0]["rule"]
        threats.append({"rule_id": rid, "description": r0["description"], "level": r0["level"], "count": len(items),
                        "threat_score": r0["level"] * len(items), "affected_agents": sorted({i["agent"]["name"] for i in items}),
                        "source_ips": sorted({(i.get("data") or {}).get("srcip") for i in items if (i.get("data") or {}).get("srcip")})[:10],
                        "mitre": r0.get("mitre"), "last_seen": items[0]["timestamp"]})
    threats.sort(key=lambda t: (t["level"] >= 12, t["threat_score"]), reverse=True)
    return {"time_range": r, "threats": threats[:limit], "total_threat_types": len(threats)}


def generate_security_report(env, args):
    kind = args.get("report_type") or "daily"
    rng = {"daily": "24h", "weekly": "7d", "monthly": "30d", "incident": "24h"}.get(kind, "24h")
    agg = get_alerts_aggregated(env, {"timestamp_start": f"now-{rng}"})
    top = get_top_security_threats(env, {"limit": 5, "time_range": rng})
    vs = get_wazuh_vulnerability_summary(env, {})
    rep = {"report_type": kind, "generated_at": iso(time.time()), "period": rng,
           "executive_summary": (f"{agg['total']} alerts in the period; {sum(x['count'] for x in agg['by_level'] if x['level'] >= 12)} critical. "
                                 f"{vs['by_severity']['Critical']} critical vulnerabilities open ({vs['cisa_kev_count']} in CISA KEV)."),
           "alert_statistics": agg, "top_threats": top["threats"], "vulnerabilities": vs,
           "agents": {"total": len(AGENTS), "active": sum(1 for a in AGENTS if env.agent_state[a["id"]]["status"] == "active")},
           "active_responses": env.ar_log[-20:]}
    if _bool(args, "include_recommendations", True):
        rep["recommendations"] = ["Patch KEV-listed CVEs on vpn-gw-01 and mail-01 first", "Enforce key-only SSH on perimeter hosts",
                                  "Investigate crypto-mining activity on k8s-node-2", "Review rundll32 beaconing on fin-ws-17"]
    return rep


# ---------------------------------------------------------------------------
# compliance
# ---------------------------------------------------------------------------
FRAMEWORK_CONTROLS = {
    "PCI-DSS": [("1.4.1", "Network security controls between trusted and untrusted networks"), ("2.2.1", "Configuration standards for system components"),
                ("6.3.3", "Security patches installed within one month"), ("8.3.6", "Password complexity"), ("10.2.1", "Audit logs capture user access"),
                ("10.4.1", "Audit logs reviewed daily"), ("11.3.1", "Internal vulnerability scans quarterly"), ("11.5.2", "Change-detection mechanism (FIM)")],
    "HIPAA": [("164.308(a)(1)", "Security management process"), ("164.312(b)", "Audit controls"), ("164.312(c)(1)", "Integrity"), ("164.312(d)", "Person or entity authentication")],
    "SOX": [("ITGC-AC-01", "Logical access provisioning"), ("ITGC-CM-02", "Change management"), ("ITGC-OP-03", "Job scheduling and monitoring")],
    "GDPR": [("Art.25", "Data protection by design"), ("Art.32", "Security of processing"), ("Art.33", "Breach notification within 72h")],
    "NIST": [("AC-7", "Unsuccessful logon attempts"), ("AU-6", "Audit record review"), ("CM-6", "Configuration settings"), ("RA-5", "Vulnerability monitoring and scanning"),
             ("SI-4", "System monitoring"), ("SI-7", "Software, firmware, and information integrity")],
    "ISO27001": [("A.5.7", "Threat intelligence"), ("A.8.8", "Management of technical vulnerabilities"), ("A.8.9", "Configuration management"),
                 ("A.8.15", "Logging"), ("A.8.16", "Monitoring activities"), ("A.5.24", "Information security incident management planning")],
}


def _control_status(env, fw, cid, aid=None):
    h = int(hashlib.md5(f"{fw}{cid}{aid}".encode()).hexdigest(), 16)
    crit_vulns = sum(1 for v in _vuln_items(env, aid) if v["vulnerability"]["severity"] == "Critical")
    fail = (h % 100) < 30 or (cid in ("6.3.3", "RA-5", "A.8.8", "11.3.1") and crit_vulns > 0)
    return "failed" if fail else ("passed" if h % 7 else "not_applicable")


def run_compliance_check(env, args):
    fw = args.get("framework") or "PCI-DSS"
    if fw not in FRAMEWORK_CONTROLS:
        raise ToolError(f"framework: must be one of {', '.join(FRAMEWORK_CONTROLS)}")
    aid = _agent(args)
    controls = []
    for cid, title in FRAMEWORK_CONTROLS[fw]:
        st = _control_status(env, fw, cid, aid)
        controls.append({"control_id": cid, "title": title, "status": st,
                         "evidence": "Automated check from SCA/syscheck/vulnerability data (mock)" if st != "not_applicable" else None})
    passed = sum(1 for c in controls if c["status"] == "passed")
    applicable = sum(1 for c in controls if c["status"] != "not_applicable")
    return {"framework": fw, "agent_id": aid or "all", "compliance_score": round(100 * passed / max(1, applicable), 1),
            "passed": passed, "failed": sum(1 for c in controls if c["status"] == "failed"), "not_applicable": len(controls) - applicable,
            "controls": controls, "checked_at": iso(time.time())}


ISO_CONTROLS = {
    "A.5.7": ("Threat intelligence", "Organizational"), "A.5.15": ("Access control", "Organizational"), "A.5.24": ("Incident management planning", "Organizational"),
    "A.5.25": ("Assessment and decision on information security events", "Organizational"), "A.8.2": ("Privileged access rights", "Technological"),
    "A.8.5": ("Secure authentication", "Technological"), "A.8.7": ("Protection against malware", "Technological"),
    "A.8.8": ("Management of technical vulnerabilities", "Technological"), "A.8.9": ("Configuration management", "Technological"),
    "A.8.15": ("Logging", "Technological"), "A.8.16": ("Monitoring activities", "Technological"), "A.8.20": ("Networks security", "Technological"),
}


def get_iso27001_dashboard(env, args):
    aid = _agent(args)
    rows = [{"control_id": cid, "title": t, "theme": th, "status": _control_status(env, "ISO", cid, aid)} for cid, (t, th) in ISO_CONTROLS.items()]
    passed = sum(1 for r in rows if r["status"] == "passed")
    return {"standard": "ISO/IEC 27001:2022", "agent_id": aid or "all", "controls_evaluated": len(rows), "passed": passed,
            "failed": sum(1 for r in rows if r["status"] == "failed"), "score": round(100 * passed / len(rows), 1), "controls": rows}


def get_iso27001_control_detail(env, args):
    cid = str(args.get("control_id") or "").strip()
    if cid not in ISO_CONTROLS:
        raise ToolError(f"control_id: unknown control '{cid}'. Known: {', '.join(ISO_CONTROLS)}")
    aid = _agent(args)
    t, th = ISO_CONTROLS[cid]
    related = {"A.8.8": ["vulnerability-detector"], "A.8.5": ["authentication_failed", "authentication_failures"], "A.8.7": ["virustotal", "rootcheck"],
               "A.8.9": ["sca", "syscheck"], "A.8.16": ["attack"], "A.8.2": ["sudo", "privilege_escalation"]}.get(cid, [])
    alerts = _filter_alerts(env, {"agent_id": aid, "rule_groups": related}, since_range("7d")) if related else []
    return {"control_id": cid, "title": t, "theme": th, "status": _control_status(env, "ISO", cid, aid),
            "related_alerts_7d": len(alerts), "sample_alerts": [compact_alert(a) for a in alerts[:5]],
            "wazuh_capabilities": related, "guidance": f"Evidence for {cid} is derived from Wazuh {', '.join(related) or 'configuration'} data (mock)."}


def get_iso27001_gap_analysis(env, args):
    d = get_iso27001_dashboard(env, args)
    gaps = [dict(c, remediation=f"Implement/verify {c['title'].lower()} and collect evidence") for c in d["controls"] if c["status"] == "failed"]
    return {"standard": d["standard"], "score": d["score"], "gaps": gaps, "gap_count": len(gaps)}


def get_iso27001_alerts(env, args):
    r = args.get("time_range") or "24h"
    if r not in ("1h", "6h", "12h", "24h", "7d", "30d"):
        raise ToolError("time_range: invalid value")
    aid = _agent(args)
    alerts = [a for a in _filter_alerts(env, {"agent_id": aid}, since_range(r)) if a["rule"]["level"] >= 7]
    mapping = {"authentication_failed": "A.8.5", "authentication_failures": "A.8.5", "vulnerability-detector": "A.8.8", "virustotal": "A.8.7",
               "rootcheck": "A.8.7", "sca": "A.8.9", "syscheck": "A.8.9", "attack": "A.8.16", "sudo": "A.8.2", "privilege_escalation": "A.8.2"}
    c = collections.Counter()
    for a in alerts:
        for g in a["rule"]["groups"]:
            if g in mapping:
                c[mapping[g]] += 1
    return {"time_range": r, "total_alerts": len(alerts), "by_control": [{"control_id": k, "title": ISO_CONTROLS[k][0], "alerts": v} for k, v in c.most_common()]}


def get_sca_policy_checks(env, args):
    aid = _agent(args, required=True)
    pid = str(args.get("policy_id") or "").strip()
    if not pid:
        raise ToolError("policy_id: required")
    a = AGENTS_BY_ID[aid]
    windows = a["os"][0] == "windows"
    checks = ([("26012", "Ensure 'Minimum password length' is set to '14 or more character(s)'"), ("26030", "Ensure 'Audit Logon' is set to 'Success and Failure'"),
               ("26101", "Ensure 'Windows Firewall: Domain: Firewall state' is set to 'On'"), ("26150", "Ensure LAPS is installed")] if windows else
              [("28570", "Ensure permissions on /etc/ssh/sshd_config are configured"), ("28580", "Ensure SSH root login is disabled"),
               ("28583", "Ensure SSH PasswordAuthentication is disabled"), ("28600", "Ensure auditd is installed"), ("28610", "Ensure AIDE is installed")])
    items = []
    for cid, title in checks:
        h = int(hashlib.md5(f"{aid}{cid}".encode()).hexdigest(), 16)
        res = "failed" if (cid in ("28583", "28580") and "perimeter" in a["groups"]) or h % 3 == 0 else "passed"
        items.append({"id": int(cid), "title": title, "result": res, "policy_id": pid, "compliance": [{"key": "cis", "value": "5.2"}, {"key": "pci_dss", "value": "2.2"}]})
    return _wazuh_list(items)


# ---------------------------------------------------------------------------
# system
# ---------------------------------------------------------------------------
def get_wazuh_statistics(env, args):
    alerts = env.snapshot()
    last_hour = [a for a in alerts if a["_ts"] > time.time() - 3600]
    return {"total_alerts_stored": len(alerts), "alerts_last_hour": len(last_hour), "events_per_second": round(len(last_hour) * 6.5 / 3600, 2),
            "agents": {"total": len(AGENTS), "active": sum(1 for a in AGENTS if env.agent_state[a["id"]]["status"] == "active"),
                       "disconnected": sum(1 for a in AGENTS if env.agent_state[a["id"]]["status"] == "disconnected")},
            "manager": {"version": WAZUH_VERSION, "uptime_seconds": int(time.time() - env.started_at), "cluster": "wazuh-cluster"},
            "active_responses_executed": len(env.ar_log)}


def get_wazuh_weekly_stats(env, args):
    alerts = _filter_alerts(env, {}, since_range("7d"))
    by_day = collections.defaultdict(lambda: collections.Counter())
    for a in alerts:
        d = a["timestamp"][:10]
        lv = a["rule"]["level"]
        by_day[d]["total"] += 1
        by_day[d]["level_12_plus" if lv >= 12 else "level_10_11" if lv >= 10 else "level_7_9" if lv >= 7 else "level_0_6"] += 1
    return {"days": [{"date": d, **dict(c)} for d, c in sorted(by_day.items())], "total": len(alerts)}


def get_wazuh_cluster_health(env, args):
    return {"enabled": True, "running": True, "name": "wazuh-cluster", "healthy": True, "nodes": 2,
            "details": {"master-node": {"status": "connected", "type": "master"}, "worker-01": {"status": "connected", "type": "worker"}}}


def get_wazuh_cluster_nodes(env, args):
    return _wazuh_list([{"name": "master-node", "type": "master", "version": WAZUH_VERSION[1:], "ip": "10.0.9.10"},
                        {"name": "worker-01", "type": "worker", "version": WAZUH_VERSION[1:], "ip": "10.0.9.11"}])


def get_wazuh_rules_summary(env, args):
    alerts = env.snapshot()
    rules = {}
    for a in alerts:
        r = a["rule"]
        rules.setdefault(r["id"], {"id": r["id"], "description": r["description"], "level": r["level"], "groups": r["groups"], "fired": 0})
        rules[r["id"]]["fired"] += 1
    lv = collections.Counter(r["level"] for r in rules.values())
    grp = collections.Counter()
    for r in rules.values():
        grp.update(r["groups"])
    return {"total_rules_loaded": 4127, "rules_fired_recently": len(rules), "by_level": dict(sorted(lv.items())),
            "top_groups": dict(grp.most_common(15)), "top_fired": sorted(rules.values(), key=lambda r: r["fired"], reverse=True)[:15]}


def get_wazuh_remoted_stats(env, args):
    n = len(env.snapshot())
    return {"data": {"affected_items": [{"queue_size": 0, "total_queue_size": 131072, "tcp_sessions": sum(1 for a in AGENTS if env.agent_state[a["id"]]["status"] == "active") - 1,
                                         "evt_count": n * 7, "ctrl_msg_count": n // 3, "discarded_count": 0, "sent_bytes": n * 912, "recv_bytes": n * 4210}]}}


def get_wazuh_log_collector_stats(env, args):
    n = len(env.snapshot())
    return {"data": {"affected_items": [{"total_events_decoded": n * 7, "syscheck_events_decoded": n // 9, "syscollector_events_decoded": n // 4,
                                         "rootcheck_events_decoded": n // 40, "sca_events_decoded": n // 30, "winevt_events_decoded": n // 5,
                                         "events_processed": n * 7, "events_dropped": 0, "alerts_written": n, "event_queue_usage": 0.02}]}}


def search_wazuh_manager_logs(env, args):
    q = str(args.get("query") or "").lower()
    if not q:
        raise ToolError("query: required")
    limit = _limit(args, 100, 1000)
    with env.lock:
        logs = [l for l in reversed(env.manager_logs) if q in (l["description"] + l["tag"]).lower()]
    return _wazuh_list(logs[:limit], total=len(logs))


def get_wazuh_manager_error_logs(env, args):
    limit = _limit(args, 100, 1000)
    with env.lock:
        logs = [l for l in reversed(env.manager_logs) if l["level"] in ("error", "warning", "critical")]
    return _wazuh_list(logs[:limit], total=len(logs))


def validate_wazuh_connection(env, args):
    return {"status": "connected", "wazuh_api": {"reachable": True, "version": WAZUH_VERSION, "latency_ms": 4},
            "wazuh_indexer": {"reachable": True, "latency_ms": 7}, "authentication": "ok", "mock": True}


# ---------------------------------------------------------------------------
# active response (write) + verification
# ---------------------------------------------------------------------------
def _dispatch(env, agents, command, srcip=None, extra=""):
    with env.lock:
        for aid in agents:
            env.active_response_alert(aid, command, srcip, extra)
        entry = {"timestamp": iso(time.time()), "command": command, "agents": agents, "srcip": srcip, "detail": extra}
        env.ar_log.append(entry)
        env._log("INFO", "wazuh-execd", f"Active response '{command}' dispatched to {','.join(agents)} {srcip or extra}")
    print(f"[mock-wazuh] ACTION {command} agents={agents} {srcip or ''} {extra}", flush=True)
    return {"data": {"affected_items": agents, "total_affected_items": len(agents), "total_failed_items": 0, "failed_items": []},
            "message": "AR command was sent to all agents" if len(agents) > 1 else "AR command was sent to the agent", "error": 0}


def _active_agents(env):
    return [a["id"] for a in AGENTS if a["id"] != "000" and env.agent_state[a["id"]]["status"] == "active"]


def wazuh_block_ip(env, args):
    ip = _ip(args.get("ip_address"))
    if args.get("duration") not in (None, 0, "0"):
        raise ToolError("duration: timed blocks are not supported; the block is permanent until removed with wazuh_firewall_allow")
    all_agents = _bool(args, "all_agents", False)
    aid = _agent(args)
    if not aid and not all_agents:
        raise ToolError("agent_id: required unless all_agents=true")
    agents = _active_agents(env) if all_agents else [aid]
    with env.lock:
        entry = env.blocked_ips.setdefault(ip, {"agents": set(), "command": "firewall-drop", "since": time.time()})
        entry["agents"].update(agents)
    return _dispatch(env, agents, "firewall-drop", ip)


def wazuh_firewall_drop(env, args):
    aid = _agent(args, required=True)
    ip = _ip(args.get("src_ip"), "src_ip")
    with env.lock:
        env.blocked_ips.setdefault(ip, {"agents": set(), "command": "firewall-drop", "since": time.time()})["agents"].add(aid)
    return _dispatch(env, [aid], "firewall-drop", ip)


def wazuh_host_deny(env, args):
    aid = _agent(args, required=True)
    ip = _ip(args.get("src_ip"), "src_ip")
    with env.lock:
        env.host_denied.setdefault(ip, set()).add(aid)
        env.blocked_ips.setdefault(ip, {"agents": set(), "command": "host-deny", "since": time.time()})["agents"].add(aid)
    return _dispatch(env, [aid], "host-deny", ip)


def wazuh_firewall_allow(env, args):
    aid = _agent(args, required=True)
    ip = _ip(args.get("src_ip"), "src_ip")
    with env.lock:
        e = env.blocked_ips.get(ip)
        if e:
            e["agents"].discard(aid)
            if not e["agents"]:
                env.blocked_ips.pop(ip, None)
    return _dispatch(env, [aid], "firewall-drop-delete", ip)


def wazuh_host_allow(env, args):
    aid = _agent(args, required=True)
    ip = _ip(args.get("src_ip"), "src_ip")
    with env.lock:
        env.host_denied.get(ip, set()).discard(aid)
        e = env.blocked_ips.get(ip)
        if e and e["command"] == "host-deny":
            e["agents"].discard(aid)
            if not e["agents"]:
                env.blocked_ips.pop(ip, None)
    return _dispatch(env, [aid], "host-deny-delete", ip)


def wazuh_isolate_host(env, args):
    aid = _agent(args, required=True)
    if aid == "000":
        raise ToolError("agent_id: refusing to isolate the manager (000)")
    with env.lock:
        env.isolated[aid] = time.time()
    return _dispatch(env, [aid], "host-isolation")


def wazuh_unisolate_host(env, args):
    aid = _agent(args, required=True)
    with env.lock:
        env.isolated.pop(aid, None)
    return _dispatch(env, [aid], "host-isolation-delete")


def wazuh_kill_process(env, args):
    aid = _agent(args, required=True)
    try:
        pid = int(args.get("process_id"))
    except (TypeError, ValueError):
        raise ToolError("process_id: must be numeric")
    with env.lock:
        proc = env.processes[aid].pop(pid, None)
    return _dispatch(env, [aid], "kill-process", extra=f"pid={pid}" + (f" ({proc['name']})" if proc else " (not found on host)"))


def wazuh_disable_user(env, args):
    aid = _agent(args, required=True)
    user = str(args.get("username") or "").strip()
    if not user:
        raise ToolError("username: required")
    with env.lock:
        env.disabled_users[(aid, user.lower())] = time.time()
    return _dispatch(env, [aid], "disable-account", extra=user)


def wazuh_enable_user(env, args):
    aid = _agent(args, required=True)
    user = str(args.get("username") or "").strip()
    with env.lock:
        env.disabled_users.pop((aid, user.lower()), None)
    return _dispatch(env, [aid], "enable-account", extra=user)


def _norm_path(p):
    return str(p).strip().lower().replace("/", "\\") if "\\" in str(p) or ":" in str(p)[:3] else str(p).strip()


def wazuh_quarantine_file(env, args):
    aid = _agent(args, required=True)
    path = str(args.get("file_path") or "").strip()
    if not path:
        raise ToolError("file_path: required")
    with env.lock:
        info = None
        for k in list(env.files[aid]):
            if _norm_path(k) == _norm_path(path):
                info = env.files[aid].pop(k)
                path = k
        env.quarantined[(aid, _norm_path(path))] = {"path": path, "since": time.time(), "info": info}
    return _dispatch(env, [aid], "quarantine-file", extra=path)


def wazuh_restore_file(env, args):
    aid = _agent(args, required=True)
    path = str(args.get("file_path") or "").strip()
    with env.lock:
        q = env.quarantined.pop((aid, _norm_path(path)), None)
        if q and q.get("info"):
            env.files[aid][q["path"]] = q["info"]
    return _dispatch(env, [aid], "restore-file", extra=path)


def wazuh_active_response(env, args):
    aid = _agent(args, required=True)
    cmd = str(args.get("command") or "").strip()
    if not cmd:
        raise ToolError("command: required")
    params = args.get("parameters") or {}
    return _dispatch(env, [aid], cmd.lstrip("!"), srcip=params.get("srcip") if isinstance(params, dict) else None, extra=str(params) if params else "")


def wazuh_restart(env, args):
    target = str(args.get("target") or "").strip()
    if not target:
        raise ToolError("target: required")
    if target in ("manager", "cluster"):
        with env.lock:
            env._log("INFO", "wazuh-control", f"Restart requested for {target}")
        print(f"[mock-wazuh] ACTION restart {target}", flush=True)
        return {"data": {"affected_items": ["master-node"] if target == "manager" else ["master-node", "worker-01"], "total_affected_items": 1 if target == "manager" else 2,
                         "total_failed_items": 0, "failed_items": []}, "message": f"Restart request sent to {target}", "error": 0}
    aid = _agent({"agent_id": target}, required=True)
    return _dispatch(env, [aid], "restart-wazuh")


def wazuh_check_blocked_ip(env, args):
    ip = _ip(args.get("ip_address"))
    aid = _agent(args)
    with env.lock:
        e = env.blocked_ips.get(ip)
        blocked = bool(e) and (aid is None or aid in e["agents"])
        n = sum(1 for a in env.alerts if "active_response" in a["rule"]["groups"] and (a.get("data") or {}).get("srcip") == ip
                and (aid is None or a["agent"]["id"] == aid))
    return {"data": {"ip_address": ip, "agent_id": aid, "scope": "agent" if aid else "fleet", "window": "now-24h", "blocked": blocked,
                     "matching_alerts": n, "blocked_on_agents": sorted(e["agents"]) if e else []}}


def wazuh_check_agent_isolation(env, args):
    aid = _agent(args, required=True)
    return {"data": {"agent_id": aid, "status": env.agent_state[aid]["status"], "isolation_confirmed": aid in env.isolated,
                     "name": AGENTS_BY_ID[aid]["name"],
                     "note": "isolation_confirmed reflects a recent host-isolation active-response alert. Connection status is not a reliable isolation signal — "
                             "a correctly isolated host keeps its manager link. Verify on the host for a definitive answer."}}


def wazuh_check_process(env, args):
    aid = _agent(args, required=True)
    try:
        pid = int(args.get("process_id"))
    except (TypeError, ValueError):
        raise ToolError("process_id: must be numeric")
    p = env.processes[aid].get(pid)
    return {"data": {"agent_id": aid, "process_id": pid, "running": p is not None, "process_name": p["name"] if p else None,
                     "note": "Based on the latest syscollector process inventory."}}


def wazuh_check_user_status(env, args):
    aid = _agent(args, required=True)
    user = str(args.get("username") or "").strip()
    disabled = (aid, user.lower()) in env.disabled_users
    exists = user.lower() in (u.lower() for u in env.users[aid]) or disabled
    return {"data": {"agent_id": aid, "username": user, "exists": exists, "disabled": disabled, "status": "disabled" if disabled else ("active" if exists else "unknown")}}


def wazuh_check_file_quarantine(env, args):
    aid = _agent(args, required=True)
    path = str(args.get("file_path") or "").strip()
    q = env.quarantined.get((aid, _norm_path(path)))
    return {"data": {"agent_id": aid, "file_path": path, "quarantined": q is not None, "quarantined_at": iso(q["since"]) if q else None,
                     "present_on_host": any(_norm_path(k) == _norm_path(path) for k in env.files[aid])}}


HANDLERS = {name: fn for name, fn in globals().items() if callable(fn) and (name.startswith(("get_", "check_", "analyze_", "search_", "perform_", "generate_", "run_", "validate_", "wazuh_")))}
