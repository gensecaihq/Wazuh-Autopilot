import re

from app.catalog import ACTIONS, mcp_arguments, missing_arguments, rollback_arguments, verify_arguments
from app.db import session_scope
from app.policy import decide
from app.settings_store import get_section, set_section
from app.swarm.mcp import ACTION_TOOL_PATTERN, is_action_tool


def _set_level(level, **extra):
    with session_scope() as db:
        p = get_section(db, "policy")
        p.update({"autonomy_level": level, **extra})
        set_section(db, "policy", p)


def test_observe_refuses_proposals(client):
    _set_level("observe")
    with session_scope() as db:
        d = decide(db, "block_ip", "185.220.101.47", {}, 0.99)
    assert not d.allowed and "observe" in d.reason


def test_recommend_is_manual_and_supervised_is_supervised(client):
    _set_level("recommend")
    with session_scope() as db:
        assert decide(db, "block_ip", "185.220.101.47", {}, 0.99).mode == "manual"
    _set_level("supervised")
    with session_scope() as db:
        assert decide(db, "block_ip", "185.220.101.47", {}, 0.99).mode == "supervised"


def test_autonomous_requires_confidence(client):
    _set_level("autonomous")
    with session_scope() as db:
        assert decide(db, "block_ip", "185.220.101.47", {}, 0.99).mode == "autonomous"
        low = decide(db, "block_ip", "185.220.101.47", {}, 0.5)
    assert low.mode == "supervised" and "confidence" in low.reason


def test_rule_override_and_agent_cap(client):
    _set_level("autonomous")
    with session_scope() as db:
        # isolate_host defaults to supervised even at autonomous level
        assert decide(db, "isolate_host", "007", {"agent_id": "007"}, 0.99).mode == "supervised"
        capped = decide(db, "block_ip", "185.220.101.47", {}, 0.99, agent_cap="recommend")
    assert capped.mode == "manual"


def test_protected_targets_and_disabled_actions(client):
    _set_level("autonomous")
    with session_scope() as db:
        assert not decide(db, "isolate_host", "000", {"agent_id": "000"}, 0.99).allowed
        assert not decide(db, "disable_user", "root", {"agent_id": "001", "username": "root"}, 0.99).allowed
        assert not decide(db, "block_ip", "127.0.0.1", {}, 0.99).allowed
        assert not decide(db, "active_response", "x", {"agent_id": "001"}, 0.99).allowed  # disabled by default


def test_mcp_arguments_match_server_schemas():
    assert mcp_arguments("block_ip", "1.2.3.4", {}) == {"ip_address": "1.2.3.4", "all_agents": True}
    assert mcp_arguments("block_ip", "1.2.3.4", {"agent_id": "001"}) == {"ip_address": "1.2.3.4", "agent_id": "001"}
    assert mcp_arguments("firewall_drop", "1.2.3.4", {"agent_id": "001"}) == {"agent_id": "001", "src_ip": "1.2.3.4"}
    assert mcp_arguments("host_deny", "", {"agent_id": "001", "ip_address": "1.2.3.4"})["src_ip"] == "1.2.3.4"
    assert mcp_arguments("kill_process", "31337", {"agent_id": "007"}) == {"agent_id": "007", "process_id": "31337"}
    assert mcp_arguments("restart_wazuh", "", {}) == {"target": "manager"}
    assert missing_arguments("disable_user", mcp_arguments("disable_user", "jdoe", {})) == ["agent_id"]


def test_verify_and_rollback_arguments():
    args = mcp_arguments("firewall_drop", "1.2.3.4", {"agent_id": "001"})
    assert verify_arguments("firewall_drop", args) == {"ip_address": "1.2.3.4", "agent_id": "001"}
    assert rollback_arguments("firewall_drop", args) == {"agent_id": "001", "src_ip": "1.2.3.4"}
    assert rollback_arguments("block_ip", {"ip_address": "1.2.3.4", "all_agents": True}) is None
    assert rollback_arguments("kill_process", {"agent_id": "1", "process_id": "2"}) is None


# Tool names from gensecaihq/Wazuh-MCP-Server v4.3.0 (toolsets.py "response" set)
WRITE_TOOLS = ["wazuh_block_ip", "wazuh_isolate_host", "wazuh_kill_process", "wazuh_disable_user",
               "wazuh_quarantine_file", "wazuh_active_response", "wazuh_firewall_drop", "wazuh_host_deny",
               "wazuh_restart", "wazuh_unisolate_host", "wazuh_enable_user", "wazuh_restore_file",
               "wazuh_firewall_allow", "wazuh_host_allow"]
CHECK_TOOLS = ["wazuh_check_blocked_ip", "wazuh_check_agent_isolation", "wazuh_check_process",
               "wazuh_check_user_status", "wazuh_check_file_quarantine"]


def test_action_tool_pattern_blocks_every_write_tool():
    assert all(is_action_tool(t) for t in WRITE_TOOLS)
    assert not any(is_action_tool(t) for t in CHECK_TOOLS)
    assert not any(is_action_tool(t) for t in ["get_wazuh_alerts", "check_ioc_reputation", "run_compliance_check"])
    assert re.compile(ACTION_TOOL_PATTERN).pattern == ACTION_TOOL_PATTERN


def test_catalog_tools_are_write_tools():
    for a in ACTIONS:
        assert a["mcp_tool"] in WRITE_TOOLS
        if a["verify_tool"]:
            assert a["verify_tool"] in CHECK_TOOLS
        if a["rollback_tool"]:
            assert a["rollback_tool"] in WRITE_TOOLS


def test_unknown_case_reference_falls_back_to_run_case(client):
    # Regression: an agent citing a case number from skill examples must not orphan its writes.
    from app.models import Case
    from app.swarm.tools import RunContext, _resolve_case
    with session_scope() as db:
        case = Case(number=9001, title="t", severity="low")
        db.add(case)
        db.flush()
        ctx = RunContext(run_id="r", case_id=case.id)
        assert _resolve_case(db, "INC-0042", ctx).id == case.id
        assert _resolve_case(db, "INC-9001", RunContext(run_id="r")).id == case.id
        assert _resolve_case(db, "INC-0042", RunContext(run_id="r")) is None


def test_nvidia_nim_provider_builds_openai_compatible_model():
    from strands.models.openai import OpenAIModel
    from app.swarm.providers import build_model
    m = build_model({"provider": "nvidia_nim", "api_key": "nvapi-test"})
    assert isinstance(m, OpenAIModel) and m.get_config()["model_id"].startswith("nvidia/nemotron")
