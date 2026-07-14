"""Expert catalog parity with desktop online Experts."""

from fastapi.testclient import TestClient

from app.catalog import list_experts, reload_catalog
from app.config import settings
from app.expert_install import ExpertInstallError, install_expert
from app.main import app


def test_list_experts_has_desktop_four(monkeypatch):
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    reload_catalog()
    body = list_experts()
    ids = [e.id for e in body.experts]
    assert ids == [
        "vidau-creative-agent-oneclick",
        "tiktok-ads-agent",
        "vidau-social-media-expert",
        "vidau-geo-agent",
    ]
    social = next(e for e in body.experts if e.id == "vidau-social-media-expert")
    assert social.availability == "coming_soon"
    assert social.status == "coming_soon"
    geo = next(e for e in body.experts if e.id == "vidau-geo-agent")
    assert "vidau-geo" in geo.requires_mcp


def test_social_install_rejected(monkeypatch):
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    reload_catalog()
    from app.catalog import get_expert_raw

    raw = get_expert_raw("vidau-social-media-expert")
    try:
        install_expert(raw)
        assert False, "expected ExpertInstallError"
    except ExpertInstallError as exc:
        assert exc.status_code == 403


def test_social_session_forbidden(monkeypatch):
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    reload_catalog()
    client = TestClient(app)
    res = client.post(
        "/v1/sessions",
        headers={"Authorization": "Bearer dev-local-token"},
        json={"expert_id": "vidau-social-media-expert"},
    )
    assert res.status_code == 403
