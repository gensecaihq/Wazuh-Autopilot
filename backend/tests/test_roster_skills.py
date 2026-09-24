from app.roster import AGENTS, EVAL_SUITES, WORKFLOWS
from app.skills_loader import builtin_skills
from app.standards import STANDARDS_BY_ID
from app.swarm.mcp import is_action_tool
from app.swarm.tools import PLATFORM_TOOL_NAMES

MCP_READ_TOOLS = {
    "get_wazuh_alerts", "get_wazuh_alert_summary", "get_alerts_aggregated", "analyze_alert_patterns",
    "search_security_events", "get_wazuh_agents", "get_wazuh_running_agents", "check_agent_health",
    "get_agent_processes", "get_agent_ports", "get_agent_configuration", "get_wazuh_vulnerabilities",
    "get_wazuh_critical_vulnerabilities", "get_wazuh_vulnerability_summary", "analyze_security_threat",
    "check_ioc_reputation", "perform_risk_assessment", "get_top_security_threats", "generate_security_report",
    "search_external_context", "run_compliance_check", "get_iso27001_dashboard", "get_iso27001_control_detail",
    "get_iso27001_gap_analysis", "get_iso27001_alerts", "get_sca_policy_checks", "get_wazuh_statistics",
    "get_wazuh_cluster_health", "get_wazuh_cluster_nodes", "get_wazuh_rules_summary", "search_wazuh_manager_logs",
    "get_wazuh_manager_error_logs", "get_wazuh_log_collector_stats", "get_wazuh_remoted_stats",
    "get_wazuh_weekly_stats", "validate_wazuh_connection", "list_wazuh_clusters",
    "wazuh_check_blocked_ip", "wazuh_check_agent_isolation", "wazuh_check_process", "wazuh_check_user_status",
    "wazuh_check_file_quarantine",
    "get_wazuh_statistics", "get_wazuh_cluster_health", "get_wazuh_cluster_nodes", "get_wazuh_remoted_stats",
    "get_wazuh_log_collector_stats", "search_wazuh_manager_logs", "get_wazuh_manager_error_logs",
    "validate_wazuh_connection", "list_wazuh_clusters",
}


def test_skills_load():
    skills = builtin_skills()
    assert len(skills) == 37
    for s in skills.values():
        assert s.description and s.instructions.strip()
        for t in s.allowed_tools or []:
            assert t in MCP_READ_TOOLS | set(PLATFORM_TOOL_NAMES) | {"handoff_to_agent"}, (s.name, t)
        for std in (s.metadata or {}).get("standards", []):
            assert std in STANDARDS_BY_ID, (s.name, std)


def test_agents_reference_real_skills_tools_and_standards():
    skills = builtin_skills()
    ids = {a["id"] for a in AGENTS}
    assert len(AGENTS) == 13
    for a in AGENTS:
        for s in a["skills"]:
            assert s in skills, (a["id"], s)
        for t in a["tools"]:
            assert not is_action_tool(t), f"{a['id']} must not hold active-response tool {t}"
            assert t in MCP_READ_TOOLS or t in PLATFORM_TOOL_NAMES, (a["id"], t)
        for std in a["standards"]:
            assert std in STANDARDS_BY_ID
        for h in a["handoffs"]:
            assert h in ids
    only_planner = [a["id"] for a in AGENTS if "propose_action" in a["tools"]]
    assert only_planner == ["response-planner"]


def test_workflows_and_evals_reference_agents():
    ids = {a["id"] for a in AGENTS}
    for w in WORKFLOWS:
        assert w["entry_agent"] in ids and w["mode"] in {"swarm", "graph"}
        step_agents = {s["agent_id"] for s in w["steps"]}
        assert step_agents <= ids
        for s in w["steps"]:
            assert set(s["next"]) <= step_agents
    for e in EVAL_SUITES:
        assert e["agent_id"] in ids


def test_ir_playbooks_are_skills_with_references():
    import pathlib
    skills = builtin_skills()
    playbooks = [n for n in skills if n.startswith("ir-playbook-")]
    assert len(playbooks) == 7
    for n in playbooks:
        ref = pathlib.Path(skills[n].path) / "references" / "playbook.md"
        assert ref.is_file() and ref.stat().st_size > 10_000, n
        assert "web_fetch" not in ref.read_text() and "OpenClaw" not in skills[n].instructions
    used = {s for a in AGENTS for s in a["skills"]}
    assert set(playbooks) <= used


def test_roster_upgrade_updates_defaults_but_keeps_customizations(client):
    # Regression: existing installs never received new built-in skills/tools on upgrade.
    from app.db import session_scope
    from app.models import AgentDef
    from app.roster import AGENTS
    from app.seed import _sync_roster
    import app.seed as seed
    with session_scope() as db:
        triage = db.get(AgentDef, "triage")
        triage.system_prompt_extra = "org note"          # not a synced field
        corr = db.get(AgentDef, "correlation")
        corr.skills = ["alert-correlation"]             # admin customization
    patched = [dict(a) for a in AGENTS]
    for a in patched:
        if a["id"] == "triage":
            a["skills"] = a["skills"] + ["wazuh-platform-health"]    # a new default ships
        if a["id"] == "correlation":
            a["skills"] = a["skills"] + ["wazuh-fim-investigation"]
    orig = seed.AGENTS
    seed.AGENTS = patched
    try:
        with session_scope() as db:
            _sync_roster(db)
        with session_scope() as db:
            assert "wazuh-platform-health" in db.get(AgentDef, "triage").skills        # default updated
            assert db.get(AgentDef, "triage").system_prompt_extra == "org note"
            assert db.get(AgentDef, "correlation").skills == ["alert-correlation"]    # customization kept
    finally:
        seed.AGENTS = orig
        with session_scope() as db:
            db.get(AgentDef, "correlation").skills = next(a for a in AGENTS if a["id"] == "correlation")["skills"]
            _sync_roster(db)
