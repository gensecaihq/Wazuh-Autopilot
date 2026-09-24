"""Dashboard, health and time-series computations."""

import time
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import utcnow
from .models import Action, AgentDef, Alert, Case, Run, Span

RANGES = {"24h": (timedelta(hours=24), timedelta(hours=1), 24), "7d": (timedelta(days=7), timedelta(days=1), 7),
          "30d": (timedelta(days=30), timedelta(days=1), 30)}
COUNTRY_CODES = {"Germany": "DE", "Russia": "RU", "Vietnam": "VN", "United States": "US", "Netherlands": "NL",
                 "China": "CN", "Brazil": "BR", "South Africa": "ZA", "Ukraine": "UA", "India": "IN", "France": "FR",
                 "United Kingdom": "GB", "Romania": "RO", "Iran": "IR", "North Korea": "KP", "Singapore": "SG",
                 "Japan": "JP", "Korea, Republic of": "KR", "South Korea": "KR", "Indonesia": "ID", "Turkey": "TR",
                 "Nigeria": "NG", "Canada": "CA", "Poland": "PL", "Hong Kong": "HK", "Bulgaria": "BG"}


def _bucket_start(dt: datetime, step: timedelta) -> datetime:
    if step >= timedelta(days=1):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(minute=0, second=0, microsecond=0)


def _buckets(rng: str):
    span, step, n = RANGES.get(rng, RANGES["24h"])
    end = _bucket_start(utcnow(), step)
    return [end - step * i for i in range(n - 1, -1, -1)], span, step


def _delta(cur: float, prev: float) -> float:
    if not prev:
        return 0.0 if not cur else 100.0
    return round((cur - prev) / prev * 100, 1)


def dashboard(db: Session, rng: str = "24h") -> dict:
    buckets, span, step = _buckets(rng)
    now = utcnow()
    since, prev_since = now - span, now - 2 * span

    def count(model, col, lo, hi, *filters):
        return db.query(func.count(model.id)).filter(col >= lo, col < hi, *filters).scalar() or 0

    alerts_cur, alerts_prev = count(Alert, Alert.ts, since, now), count(Alert, Alert.ts, prev_since, since)
    inc_cur, inc_prev = count(Case, Case.created_at, since, now), count(Case, Case.created_at, prev_since, since)
    auto_cur = count(Action, Action.created_at, since, now, Action.auto_approved.is_(True), Action.status.in_(["executed", "verified"]))
    auto_prev = count(Action, Action.created_at, prev_since, since, Action.auto_approved.is_(True), Action.status.in_(["executed", "verified"]))

    def mttr(lo, hi):
        rows = db.query(Case.created_at, Case.resolved_at).filter(Case.resolved_at.is_not(None), Case.created_at >= lo,
                                                                 Case.created_at < hi).all()
        vals = [(r - c).total_seconds() / 60 for c, r in rows if r and c]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    mttr_cur, mttr_prev = mttr(since, now), mttr(prev_since, since)
    pending = db.query(func.count(Action.id)).filter(Action.status == "proposed").scalar() or 0

    index = {b: {"ts": b.isoformat(), "alerts": 0, "incidents": 0, "actions": 0, "blocked": 0} for b in buckets}
    for (ts,) in db.query(Alert.ts).filter(Alert.ts >= buckets[0]).all():
        b = _bucket_start(ts, step)
        if b in index:
            index[b]["alerts"] += 1
    for (ts,) in db.query(Case.created_at).filter(Case.created_at >= buckets[0]).all():
        b = _bucket_start(ts, step)
        if b in index:
            index[b]["incidents"] += 1
    for ts, typ, status in db.query(Action.created_at, Action.type, Action.status).filter(Action.created_at >= buckets[0]).all():
        b = _bucket_start(ts, step)
        if b in index:
            index[b]["actions"] += 1
            if typ in {"block_ip", "firewall_drop", "host_deny"} and status in {"executed", "verified"}:
                index[b]["blocked"] += 1

    sev = dict(db.query(Alert.severity, func.count(Alert.id)).filter(Alert.ts >= since).group_by(Alert.severity).all())
    src_rows = (db.query(Alert.src_country, func.avg(Alert.src_lat), func.avg(Alert.src_lon), func.count(Alert.id))
                .filter(Alert.ts >= since, Alert.src_country.is_not(None)).group_by(Alert.src_country)
                .order_by(func.count(Alert.id).desc()).limit(12).all())
    total_src = sum(r[3] for r in src_rows) or 1
    targets = (db.query(Alert.agent_id, Alert.agent_name, Alert.agent_ip, func.count(Alert.id),
                        func.count(func.distinct(Alert.case_id)))
               .filter(Alert.ts >= since, Alert.agent_id.is_not(None))
               .group_by(Alert.agent_id, Alert.agent_name, Alert.agent_ip).order_by(func.count(Alert.id).desc()).limit(10).all())
    prev_by_agent = dict(db.query(Alert.agent_id, func.count(Alert.id)).filter(Alert.ts >= prev_since, Alert.ts < since)
                         .group_by(Alert.agent_id).all())
    mitre_counts: dict[str, dict] = {}
    for (mitre,) in db.query(Case.mitre).filter(Case.created_at >= since).all():
        for t in mitre or []:
            k = t.get("technique_id")
            if k:
                e = mitre_counts.setdefault(k, {"technique_id": k, "name": t.get("name", ""), "tactic": t.get("tactic", ""), "count": 0})
                e["count"] += 1
    runs = db.query(Run.status, Run.tokens_in, Run.tokens_out, Run.cost_usd).filter(Run.started_at >= now - timedelta(hours=24)).all()
    done = [r for r in runs if r[0] in {"completed", "failed"}]
    agents_total = db.query(func.count(AgentDef.id)).filter(AgentDef.enabled.is_(True)).scalar() or 0
    active_agents = db.query(func.count(func.distinct(Span.agent_id))).filter(
        Span.started_at >= now - timedelta(minutes=10), Span.kind == "agent").scalar() or 0
    return {
        "kpis": {
            "alerts": {"value": alerts_cur, "delta_pct": _delta(alerts_cur, alerts_prev)},
            "incidents": {"value": inc_cur, "delta_pct": _delta(inc_cur, inc_prev)},
            "auto_contained": {"value": auto_cur, "delta_pct": _delta(auto_cur, auto_prev)},
            "mttr_minutes": {"value": mttr_cur, "delta_pct": _delta(mttr_cur, mttr_prev)},
            "pending_approvals": {"value": pending, "delta_pct": 0},
        },
        "traffic": list(index.values()),
        "severity_breakdown": [{"severity": s, "count": sev.get(s, 0)} for s in ["critical", "high", "medium", "low", "informational"]],
        "attack_sources": [{"country": COUNTRY_CODES.get(c, (c or "??")[:2].upper()), "country_name": c, "lat": lat, "lon": lon,
                            "count": n, "pct": round(n / total_src * 100, 1)} for c, lat, lon, n in src_rows],
        "top_targets": [{"agent_id": a, "agent_name": name, "ip": ip, "alerts": n, "incidents": cases,
                         "trend_pct": _delta(n, prev_by_agent.get(a, 0))} for a, name, ip, n, cases in targets],
        "mitre_top": sorted(mitre_counts.values(), key=lambda e: -e["count"])[:8],
        "swarm": {"agents_total": agents_total, "agents_active": active_agents, "runs_24h": len(runs),
                  "success_rate": round(sum(1 for r in done if r[0] == "completed") / len(done), 3) if done else 1.0,
                  "tokens_24h": sum((r[1] or 0) + (r[2] or 0) for r in runs),
                  "cost_24h_usd": round(sum(r[3] or 0 for r in runs), 2)},
    }


def agent_health(db: Session, running_agents: set[str] | None = None) -> dict[str, dict]:
    since = utcnow() - timedelta(hours=24)
    rows = db.query(Span.agent_id, Span.kind, Span.status, Span.duration_ms, Span.tokens_in, Span.tokens_out,
                    Span.started_at, Span.error).filter(Span.started_at >= since, Span.agent_id.is_not(None)).all()
    per: dict[str, dict] = defaultdict(lambda: {"runs": 0, "errors": 0, "lat": [], "tokens": 0, "tin": 0, "tout": 0,
                                                "last": None, "last_error": None})
    for agent, kind, status, dur, tin, tout, started, err in rows:
        p = per[agent]
        if kind == "agent":
            p["runs"] += 1
            p["lat"].append(dur or 0)
            p["last"] = max(p["last"], started) if p["last"] else started
        if status == "error":
            p["errors"] += 1
            p["last_error"] = err
        p["tin"] += tin or 0
        p["tout"] += tout or 0
    out = {}
    for agent in [a for (a,) in db.query(AgentDef.id).all()]:
        p = per.get(agent)
        running = agent in (running_agents or set())
        if not p or not p["runs"]:
            out[agent] = {"status": "idle", "score": 100, "runs_24h": 0, "error_rate": 0.0, "avg_latency_ms": 0,
                          "p95_latency_ms": 0, "tokens_24h": 0, "cost_24h_usd": 0.0, "last_run_at": None,
                          "last_error": None, "_status": "running" if running else "idle"}
            continue
        lat = sorted(p["lat"])
        err_rate = round(p["errors"] / max(1, p["runs"] + p["errors"]), 3)
        p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]
        score = max(0, int(100 - err_rate * 300 - max(0, (p95 - 60000) / 2000)))
        status = "healthy" if score >= 80 else "degraded" if score >= 50 else "down"
        out[agent] = {"status": status, "score": score, "runs_24h": p["runs"], "error_rate": err_rate,
                      "avg_latency_ms": int(sum(lat) / len(lat)), "p95_latency_ms": p95,
                      "tokens_24h": p["tin"] + p["tout"],
                      "cost_24h_usd": round(p["tin"] / 1e6 * 3 + p["tout"] / 1e6 * 15, 3),
                      "last_run_at": p["last"].isoformat() if p["last"] else None, "last_error": p["last_error"],
                      "_status": "running" if running else ("error" if status == "down" else "idle")}
    return out


def agent_metrics_7d(db: Session, agent_id: str) -> list[dict]:
    since = (utcnow() - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    days = {(since + timedelta(days=i)).date().isoformat(): {"day": (since + timedelta(days=i)).date().isoformat(),
                                                             "runs": 0, "errors": 0, "avg_latency_ms": 0, "tokens": 0, "_lat": []}
            for i in range(7)}
    for kind, status, dur, tin, tout, started in db.query(Span.kind, Span.status, Span.duration_ms, Span.tokens_in,
                                                          Span.tokens_out, Span.started_at).filter(
            Span.agent_id == agent_id, Span.started_at >= since).all():
        d = days.get(started.date().isoformat())
        if not d:
            continue
        if kind == "agent":
            d["runs"] += 1
            d["_lat"].append(dur or 0)
        if status == "error":
            d["errors"] += 1
        d["tokens"] += (tin or 0) + (tout or 0)
    for d in days.values():
        lat = d.pop("_lat")
        d["avg_latency_ms"] = int(sum(lat) / len(lat)) if lat else 0
    return list(days.values())


def timeseries(db: Session, metric: str, rng: str, agent_id: str | None = None) -> dict:
    buckets, span, step = _buckets(rng)
    start = buckets[0]
    q = db.query(Span).filter(Span.started_at >= start)
    if agent_id:
        q = q.filter(Span.agent_id == agent_id)
    totals = {b: 0.0 for b in buckets}
    counts = {b: 0 for b in buckets}
    by_agent: dict[str, dict] = defaultdict(lambda: {b: 0.0 for b in buckets})
    for s in q.all():
        b = _bucket_start(s.started_at, step)
        if b not in totals:
            continue
        if metric == "runs" and s.kind == "run":
            v = 1
        elif metric == "tokens":
            v = (s.tokens_in or 0) + (s.tokens_out or 0)
        elif metric == "latency" and s.kind == "agent":
            v = s.duration_ms or 0
        elif metric == "errors" and s.status == "error":
            v = 1
        elif metric == "cost":
            v = (s.tokens_in or 0) / 1e6 * 3 + (s.tokens_out or 0) / 1e6 * 15
        elif metric == "tool_calls" and s.kind in {"tool", "handoff"}:
            v = 1
        else:
            continue
        totals[b] += v
        counts[b] += 1
        if s.agent_id:
            by_agent[s.agent_id][b] += v
    if metric == "latency":
        totals = {b: (totals[b] / counts[b] if counts[b] else 0) for b in buckets}
    return {"metric": metric, "points": [{"ts": b.isoformat(), "value": round(totals[b], 4)} for b in buckets],
            "by_agent": [{"agent_id": a, "points": [{"ts": b.isoformat(), "value": round(v[b], 4)} for b in buckets]}
                         for a, v in by_agent.items()]}


def prometheus(db: Session) -> str:
    lines = []

    def g(name, help_, value, labels=""):
        lines.append(f"# HELP {name} {help_}\n# TYPE {name} gauge\n{name}{labels} {value}")

    g("autopilot_cases_open", "Open cases", db.query(func.count(Case.id)).filter(
        Case.status.notin_(["resolved", "closed", "false_positive"])).scalar() or 0)
    g("autopilot_actions_pending", "Actions awaiting approval",
      db.query(func.count(Action.id)).filter(Action.status == "proposed").scalar() or 0)
    for status, n in db.query(Run.status, func.count(Run.id)).group_by(Run.status).all():
        lines.append(f'autopilot_runs_total{{status="{status}"}} {n}')
    for agent, n, t in db.query(Span.agent_id, func.count(Span.id), func.sum(Span.tokens_in + Span.tokens_out)).filter(
            Span.kind == "agent", Span.agent_id.is_not(None)).group_by(Span.agent_id).all():
        lines.append(f'autopilot_agent_invocations_total{{agent="{agent}"}} {n}')
    lines.append(f"autopilot_scrape_timestamp {int(time.time())}")
    return "\n".join(lines) + "\n"
