from app.llm_config import LlmConfig, effective_llm_mode, resolve_llm_config
from app.config import settings


def test_resolve_prefers_cloud_agent_env(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "https://example.com/v1")
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    cfg = resolve_llm_config()
    assert cfg.ok
    assert cfg.base_url == "https://example.com/v1"
    assert cfg.model == "test-model"
    assert cfg.source.startswith("env:")


def test_effective_llm_mode_stub(monkeypatch):
    monkeypatch.setattr(settings, "llm_mode", "stub")
    assert effective_llm_mode() == "stub"


def test_llm_config_skips_moderation_model(tmp_path, monkeypatch):
    from app.config import settings
    from app import account_store

    monkeypatch.setattr(account_store, "OPENVIDAU_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "llm_mode", "auto")
    monkeypatch.setattr(settings, "vidau_home", str(tmp_path))
    (tmp_path / ".env").write_text(
        "OPENVIDAU_API_KEY=sk-x\nOPENVIDAU_BASE_URL=https://open.vidau.ai/v1\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "model:\n  default: omni-moderation-latest\n  provider: openvidau\n",
        encoding="utf-8",
    )
    cfg = resolve_llm_config()
    assert cfg.ok
    assert "moderation" not in cfg.model
    assert cfg.model == "gpt-4o-mini"
