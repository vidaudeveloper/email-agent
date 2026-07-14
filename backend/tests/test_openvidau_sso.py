"""Tests for OpenVidAU SSO proxy + llm_config from openvidau.env."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import account_store
from app.llm_config import resolve_llm_config
from app.main import app

client = TestClient(app)


def test_login_ticket_proxies_upstream(tmp_path, monkeypatch):
    monkeypatch.setattr(account_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(account_store, "ACCOUNT_AUTH_FILE", tmp_path / "account_auth.json")
    monkeypatch.setattr(account_store, "OPENVIDAU_ENV_FILE", tmp_path / "openvidau.env")
    monkeypatch.setattr(account_store, "CLOUD_SESSIONS_FILE", tmp_path / "cloud_sessions.json")

    with patch("app.openvidau_sso._request") as req:
        req.return_value = {
            "ticket": "lt_test",
            "expires_in": 300,
            "poll_interval_ms": 1500,
        }
        r = client.post("/v1/auth/login-ticket", json={"locale": "zh"})
    assert r.status_code == 200
    body = r.json()
    assert body["ticket"] == "lt_test"
    assert "login_url" in body
    assert "login_ticket=lt_test" in body["login_url"]


def test_poll_signed_in_bootstraps_key(tmp_path, monkeypatch):
    monkeypatch.setattr(account_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(account_store, "ACCOUNT_AUTH_FILE", tmp_path / "account_auth.json")
    monkeypatch.setattr(account_store, "OPENVIDAU_ENV_FILE", tmp_path / "openvidau.env")
    monkeypatch.setattr(account_store, "CLOUD_SESSIONS_FILE", tmp_path / "cloud_sessions.json")

    def fake_request(method, path, **kwargs):
        if path.endswith("poll"):
            return {
                "session": {
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "user": {"id": "u1", "email": "a@b.com", "name": "A"},
                    "account": {"plan": "pro", "status": "active"},
                }
            }
        if path.endswith("bootstrap"):
            return {
                "vidau_user_id": "u1",
                "account": {"plan": "pro", "status": "active"},
                "provider": {
                    "id": "openvidau",
                    "api_key": "sk-from-bootstrap",
                    "base_url": "https://open.vidau.ai/v1",
                    "default_model": "gpt-4o-mini",
                    "models": ["gpt-4o-mini"],
                },
            }
        raise AssertionError(path)

    with patch("app.openvidau_sso._request", side_effect=fake_request):
        r = client.post(
            "/v1/auth/login-ticket/poll",
            json={"ticket": "lt_test"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "signed_in"
    assert body["session_token"]
    assert body["llm"]["configured"] is True
    assert "sk-from-bootstrap" not in str(body)  # key must not leak to client
    env_text = (tmp_path / "openvidau.env").read_text()
    assert "sk-from-bootstrap" in env_text

    # Session token authorizes API
    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['session_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["llm"]["configured"] is True


def test_llm_config_reads_openvidau_env(tmp_path, monkeypatch):
    monkeypatch.setattr(account_store, "OPENVIDAU_ENV_FILE", tmp_path / "openvidau.env")
    (tmp_path / "openvidau.env").write_text(
        "OPENVIDAU_API_KEY=sk-test\n"
        "OPENVIDAU_BASE_URL=https://open.vidau.ai/v1\n"
        "OPENVIDAU_DEFAULT_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )
    # Clear competing settings
    from app.config import settings

    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "llm_mode", "auto")

    cfg = resolve_llm_config()
    assert cfg.ok
    assert cfg.api_key == "sk-test"
    assert cfg.model == "deepseek-v4-pro"
    assert cfg.source == "sso:openvidau.env"
