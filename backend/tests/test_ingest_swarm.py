import copy

from conftest import wait_for

from app.db import session_scope
from app.settings_store import get_section, set_section

ALERT = {"id": "t-1", "timestamp": "2026-09-23T20:10:00Z",
         "rule": {"id": "5712", "level": 12, "description": "sshd: brute force trying to get access to the system.",
                  "groups": ["sshd", "authentication_failures"],
                  "mitre": {"id": ["T1110"], "tactic": ["Credential Access"], "technique": ["Brute Force"]}},
         "agent": {"id": "001", "name": "web-prod-01", "ip": "10.0.1.11"},
         "data": {"srcip": "185.220.101.47", "dstuser": "root"},
         "GeoLocation": {"country_name": "Germany", "location": {"lat": 51.3, "lon": 9.5}}}


def _alert(i, **over):
    a = copy.deepcopy(ALERT)
    a["id"] = f"t-{i}"
    for k, v in over.items():
        a[k] = v
    return a


def test_ingest_groups_and_triggers_swarm(client, admin):
    with session_scope() as db:
        p = get_section(db, "policy")
        p["autonomy_level"] = "supervised"
        set_section(db, "policy", p)
    r = client.post("/api/v1/ingest/wazuh", headers=admin, json=[_alert(1), _alert(2)])
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 2 and len(body["case_ids"]) == 1  # second alert grouped into the same case
    case_id = body["case_ids"][0]

    def run_done():
        runs = client.get(f"/api/v1/runs?case_id={case_id}", headers=admin).json()["items"]
        return runs if runs and runs[0]["status"] in {"completed", "failed"} else None

    runs = wait_for(run_done, timeout=60)
    run = client.get(f"/api/v1/runs/{runs[0]['id']}", headers=admin).json()
    assert run["status"] == "completed", run.get("error")
    assert run["mode"] == "swarm"
    assert [h["to"] for h in run["handoffs"]][:2] == ["correlation", "investigation"]
    assert "response-planner" in run["agents"]
    kinds = {s["kind"] for s in run["spans"]}
    assert {"run", "agent", "model", "tool", "handoff"} <= kinds

    case = client.get(f"/api/v1/cases/{case_id}", headers=admin).json()
    assert case["alert_count"] == 2
    assert any(e["value"] == "185.220.101.47" for e in case["entities"])
    assert case["findings"] and case["mitre"]
    actions = case["actions"]
    assert actions and actions[0]["type"] == "block_ip" and actions[0]["status"] == "proposed"
    assert actions[0]["autonomy"] == "supervised"


def test_duplicate_and_low_level_alerts(client, admin):
    r = client.post("/api/v1/ingest/wazuh", headers=admin, json=[_alert(1)]).json()
    assert r["accepted"] == 0  # same wazuh id
    low = _alert(99, rule={**ALERT["rule"], "id": "5501", "level": 3, "description": "PAM: Login session opened."})
    r = client.post("/api/v1/ingest/wazuh", headers=admin, json=[low]).json()
    assert r["accepted"] == 1 and r["case_ids"] == []


def test_ingest_key_header(client, admin):
    with session_scope() as db:
        key = get_section(db, "ingestion")["ingest_key"]
    assert client.post("/api/v1/ingest/wazuh", json=[_alert(500)]).status_code == 401
    r = client.post("/api/v1/ingest/wazuh", headers={"X-Autopilot-Ingest-Key": key}, json=[_alert(501, rule={
        **ALERT["rule"], "level": 3})])
    assert r.status_code == 200


def test_approval_flow_and_two_person_rule(client, admin, make_user):
    responder = make_user("responder")
    action = wait_for(lambda: next(iter(client.get("/api/v1/actions?status=proposed", headers=admin).json()["items"]), None))
    # reject path on a copy-less flow: approve then execute (no MCP configured -> execution fails cleanly)
    with session_scope() as db:
        p = get_section(db, "policy")
        p["require_two_person"] = True
        set_section(db, "policy", p)
    r = client.post(f"/api/v1/actions/{action['id']}/approve", headers=responder, json={"note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # supervised actions execute automatically after approval; without an MCP server this fails and is recorded
    done = wait_for(lambda: (a := client.get(f"/api/v1/actions/{action['id']}", headers=admin).json())["status"]
                    in {"failed", "executed", "verified"} and a)
    assert done["status"] == "failed" and done["result"].get("error")
    audit = client.get("/api/v1/audit?action=action.", headers=admin).json()["items"]
    assert {"action.approved", "action.failed"} <= {a["action"] for a in audit}


def test_dry_run_playground(client, admin):
    s = client.post("/api/v1/playground/sessions", headers=admin, json={"agent_id": "vuln-management", "dry_run": True}).json()
    run_id = client.post(f"/api/v1/playground/sessions/{s['session_id']}/messages", headers=admin,
                         json={"content": "Prioritize critical vulnerabilities"}).json()["run_id"]
    run = wait_for(lambda: (r := client.get(f"/api/v1/runs/{run_id}", headers=admin).json())["status"]
                   in {"completed", "failed"} and r)
    assert run["status"] == "completed", run.get("error")
    assert run["dry_run"] is True
    reports = client.get("/api/v1/reports", headers=admin).json()
    assert all(rep["run_id"] != run_id for rep in reports["items"])  # dry run wrote nothing
    msgs = client.get(f"/api/v1/playground/sessions/{s['session_id']}", headers=admin).json()["messages"]
    assert any(m["role"] == "tool" for m in msgs)


def test_eval_suite_runs(client, admin):
    er = client.post("/api/v1/evals/suites/response-planning/run", headers=admin).json()
    done = wait_for(lambda: (r := client.get(f"/api/v1/evals/runs/{er['id']}", headers=admin).json())["status"]
                    in {"completed", "failed"} and r, timeout=60)
    assert done["status"] == "completed", done.get("error")
    assert done["results"][0]["passed"] is True


def test_dashboard_and_health(client, admin):
    d = client.get("/api/v1/dashboard/summary?range=24h", headers=admin).json()
    assert len(d["traffic"]) == 24 and d["kpis"]["incidents"]["value"] >= 1
    h = client.get("/api/v1/system/health", headers=admin).json()
    assert {c["id"] for c in h["components"]} >= {"database", "wazuh_mcp", "model", "ingestion"}
    agents = client.get("/api/v1/agents", headers=admin).json()["items"]
    triage = next(a for a in agents if a["id"] == "triage")
    assert triage["health"]["runs_24h"] >= 1
    assert "autopilot_runs_total" in client.get("/metrics").text


def test_runs_record_token_usage(client, admin):
    # Regression: Strands updates usage after AfterModelCallEvent; totals must still be captured.
    runs = client.get("/api/v1/runs?workflow_id=incident-response&status=completed", headers=admin).json()["items"]
    assert runs and runs[0]["tokens_in"] > 0 and runs[0]["tokens_out"] > 0
    run = client.get(f"/api/v1/runs/{runs[0]['id']}", headers=admin).json()
    model_spans = [s for s in run["spans"] if s["kind"] == "model"]
    assert sum(s["tokens_in"] for s in model_spans) == run["tokens_in"]
