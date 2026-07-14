"""TikTok chat should not require MCP apiKey upfront (desktop-aligned)."""

from app.catalog import get_expert, reload_catalog
from app.config import settings
from app.sessions import create_session


def test_tiktok_ready_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "mcp_mode", "real")
    reload_catalog()
    expert = get_expert("tiktok-ads-agent")
    # Installed from previous parity install; if not, status may be needs_setup
    if expert.installed:
        assert expert.status == "ready"
        assert "tiktok-ads-agent" in (expert.mcp_credentials_missing or [])
        session = create_session("tiktok-ads-agent")
        assert session.status == "ready"
        assert "tiktok-ads-agent" in session.missing_credentials
