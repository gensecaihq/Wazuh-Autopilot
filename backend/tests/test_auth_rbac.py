from conftest import login


def test_login_and_me(client, admin):
    me = client.get("/api/v1/auth/me", headers=admin).json()
    assert me["role"] == "admin"
    assert "users:manage" in me["permissions"]


def test_bad_login_is_rejected_and_audited(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "wrong"})
    assert r.status_code == 401
    audit = client.get("/api/v1/audit?action=auth.failed", headers=admin).json()
    assert audit["total"] >= 1


def test_requests_without_token_are_401(client):
    assert client.get("/api/v1/cases").status_code == 401


def test_analyst_cannot_approve_or_change_policy(client, make_user):
    analyst = make_user("analyst")
    assert client.get("/api/v1/cases", headers=analyst).status_code == 200
    assert client.post("/api/v1/actions/nope/approve", headers=analyst, json={}).status_code == 403
    assert client.put("/api/v1/policy", headers=analyst, json={"autonomy_level": "autonomous"}).status_code == 403
    assert client.get("/api/v1/settings", headers=analyst).status_code == 403


def test_auditor_is_read_only(client, make_user):
    auditor = make_user("auditor")
    assert client.get("/api/v1/audit", headers=auditor).status_code == 200
    assert client.get("/api/v1/settings", headers=auditor).status_code == 200
    assert client.patch("/api/v1/agents/triage", headers=auditor, json={"enabled": False}).status_code == 403
    assert client.post("/api/v1/workflows/alert-triage/run", headers=auditor, json={}).status_code == 403


def test_soc_manager_cannot_manage_users(client, make_user):
    mgr = make_user("soc_manager")
    assert client.post("/api/v1/users", headers=mgr, json={"email": "x@y.z", "name": "x", "role": "admin",
                                                          "password": "Whatever-123"}).status_code == 403
    # but gets the name directory for assignee pickers
    users = client.get("/api/v1/users", headers=mgr).json()["items"]
    assert users and "email" not in users[0]


def test_api_token_auth(client, admin):
    tok = client.post("/api/v1/api-tokens", headers=admin, json={"name": "ci", "role": "auditor"}).json()
    assert tok["token"].startswith("apk_")
    h = {"Authorization": f"Bearer {tok['token']}"}
    assert client.get("/api/v1/audit", headers=h).status_code == 200
    assert client.put("/api/v1/policy", headers=h, json={}).status_code == 403


def test_secrets_are_masked(client, admin):
    client.put("/api/v1/settings", headers=admin, json={"wazuh": {"api_key": "wazuh_supersecret_abcd"}})
    s = client.get("/api/v1/settings", headers=admin).json()
    assert s["wazuh"]["api_key"] == "••••abcd"
    # sending the mask back keeps the real value
    client.put("/api/v1/settings", headers=admin, json={"wazuh": {"api_key": "••••abcd", "mcp_url": ""}})
    from app.db import session_scope
    from app.settings_store import get_section
    with session_scope() as db:
        assert get_section(db, "wazuh")["api_key"] == "wazuh_supersecret_abcd"


def test_setup_is_locked_after_completion(client):
    assert client.get("/api/v1/setup/status").json()["setup_complete"] is True
    r = client.post("/api/v1/setup/complete", json={"org_name": "x", "admin_email": "a@b.c", "admin_name": "a",
                                                    "admin_password": "Password-1234"})
    assert r.status_code == 409


def test_change_password(client, make_user):
    # Regression: an edit once pointed this endpoint's return at an undefined variable.
    h = make_user("analyst")
    r = client.post("/api/v1/auth/change-password", headers=h,
                    json={"current_password": "User-Pass-1234", "new_password": "New-User-Pass-5678"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    bad = client.post("/api/v1/auth/change-password", headers=h,
                      json={"current_password": "wrong", "new_password": "Another-Pass-999"})
    assert bad.status_code == 400
