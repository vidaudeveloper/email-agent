from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_experts_contains_tiktok():
    r = client.get("/v1/experts", headers={"Authorization": "Bearer dev-local-token"})
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()["experts"]]
    assert "tiktok-ads-agent" in ids
    assert "vidau-creative-agent-oneclick" in ids


def test_expert_status_fields():
    r = client.get("/v1/experts/tiktok-ads-agent", headers={"Authorization": "Bearer dev-local-token"})
    body = r.json()
    assert body["id"] == "tiktok-ads-agent"
    assert "requires_mcp" in body
    assert "tiktok-ads-agent" in body["requires_mcp"]
    assert body["sandbox_policy"] in ("never", "on_demand", "always")
    assert "installed" in body
    assert "mcp_mode" in body


def test_health_exposes_mcp_and_llm():
    r = client.get("/health")
    body = r.json()
    assert body["ok"] is True
    assert "mcp_mode" in body
    assert "llm_configured" in body
    assert "llm_mode" in body
