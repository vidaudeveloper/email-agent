from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-token"}


def test_create_session_with_expert():
    r = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "tiktok-ads-agent"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["status"] == "ready"
    assert body["sandbox"]["provider"] == "none"
    assert body["sandbox"]["allocated"] is False
    assert body["mcp_mode"] == "mock"
    assert "llm_mode" in body
