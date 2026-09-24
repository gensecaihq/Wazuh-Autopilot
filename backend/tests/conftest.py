import os
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="autopilot-test-")
os.environ.update({
    "AUTOPILOT_DATA_DIR": _tmp,
    "AUTOPILOT_DEMO_MODE": "false",
    "AUTOPILOT_SEED_HISTORY": "false",
    "AUTOPILOT_SCHEDULER": "false",
    "AUTOPILOT_ADMIN_PASSWORD": "Admin-Pass-1234",
    "AUTOPILOT_ADMIN_EMAIL": "admin@test.local",
    "MODEL_PROVIDER": "demo",
    "AUTOPILOT_DEMO_LATENCY_MS": "0,5",
    "WAZUH_MCP_URL": "",
    "AUTOPILOT_UI_DIST": os.path.join(_tmp, "no-ui"),
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email="admin@test.local", password="Admin-Pass-1234") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return login(client)


@pytest.fixture(scope="session")
def make_user(client, admin):
    def _make(role: str) -> dict:
        email = f"{role}-{time.time_ns()}@test.local"
        r = client.post("/api/v1/users", headers=admin,
                        json={"email": email, "name": role.title(), "role": role, "password": "User-Pass-1234"})
        assert r.status_code == 200, r.text
        return login(client, email, "User-Pass-1234")
    return _make


def wait_for(fn, timeout=30.0, interval=0.2):
    end = time.time() + timeout
    while time.time() < end:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError("condition not met in time")
