"""Resolve OpenAI-compatible LLM settings from SSO env, CLOUD_AGENT_*, or ~/.vidau."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.account_store import load_openvidau_env
from app.config import settings


@dataclass
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    source: str

    @property
    def ok(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def _vidau_home() -> Path:
    if settings.vidau_home:
        return Path(settings.vidau_home).expanduser()
    return Path.home() / ".vidau"


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _key_from_auth_pool(provider: str) -> str | None:
    auth_path = _vidau_home() / "auth.json"
    if not auth_path.exists():
        return None
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    pool = (data.get("credential_pool") or {}).get(provider) or []
    if not pool:
        return None
    for entry in pool:
        source = str(entry.get("source") or "")
        if source.startswith("env:"):
            env_name = source.split(":", 1)[1]
            val = os.environ.get(env_name, "").strip()
            if val:
                return val
        secret = entry.get("api_key") or entry.get("secret")
        if secret:
            return str(secret)
    return None


def _load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        return {}
    return out


def _is_chat_model(model: str) -> bool:
    name = (model or "").strip().lower()
    if not name:
        return False
    # Moderation / embedding / whisper are not usable for tool-calling chat
    blocked = ("moderation", "embedding", "whisper", "tts-", "dall-e", "realtime")
    return not any(b in name for b in blocked)


def _pick_model(*candidates: str) -> str:
    for raw in candidates:
        model = (raw or "").strip()
        if model and _is_chat_model(model):
            return model
    return "gpt-4o-mini"


def resolve_llm_config() -> LlmConfig:
    # 1) Explicit cloud-agent env wins
    if settings.llm_base_url and settings.llm_api_key and settings.llm_model:
        return LlmConfig(
            base_url=settings.llm_base_url.rstrip("/"),
            api_key=settings.llm_api_key,
            model=_pick_model(settings.llm_model),
            source="env:CLOUD_AGENT_LLM_*",
        )

    # 2) SSO bootstrap file written by Cloud Agent
    sso_env = load_openvidau_env()
    if sso_env.get("OPENVIDAU_API_KEY"):
        return LlmConfig(
            base_url=(
                sso_env.get("OPENVIDAU_BASE_URL")
                or "https://open.vidau.ai/v1"
            ).rstrip("/"),
            api_key=sso_env["OPENVIDAU_API_KEY"],
            model=_pick_model(
                sso_env.get("OPENVIDAU_DEFAULT_MODEL", ""),
                settings.llm_model,
            ),
            source="sso:openvidau.env",
        )

    # 3) Process env + ~/.vidau/.env (desktop may have logged in on same machine)
    home_env = _load_dotenv_file(_vidau_home() / ".env")
    api_key = (
        settings.llm_api_key
        or os.environ.get("OPENVIDAU_API_KEY", "").strip()
        or home_env.get("OPENVIDAU_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
        or ""
    )

    cfg = _read_yaml(_vidau_home() / "config.yaml")
    model_block = cfg.get("model") or {}
    model = str(model_block.get("default") or "").strip()
    provider = str(model_block.get("provider") or "").strip()
    base_url = str(model_block.get("base_url") or "").strip()

    if not api_key and provider:
        api_key = _key_from_auth_pool(provider) or ""

    if not base_url:
        base_url = (
            home_env.get("OPENVIDAU_BASE_URL", "").strip()
            or os.environ.get("OPENVIDAU_BASE_URL", "").strip()
            or os.environ.get("OPENAI_BASE_URL", "").strip()
        )
    if not base_url and (provider == "openvidau" or api_key):
        base_url = "https://open.vidau.ai/v1"
    if not base_url:
        base_url = "https://api.openai.com/v1"

    model = _pick_model(
        settings.llm_model,
        home_env.get("OPENVIDAU_DEFAULT_MODEL", ""),
        model,
    )

    source = "vidau:.env" if home_env.get("OPENVIDAU_API_KEY") else (
        f"vidau:{provider}" if provider else "defaults"
    )
    if os.environ.get("OPENVIDAU_API_KEY"):
        source = "env:OPENVIDAU_API_KEY"

    return LlmConfig(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        source=source,
    )


def effective_llm_mode() -> str:
    mode = (settings.llm_mode or "auto").strip().lower()
    if mode in {"stub", "openai_compatible"}:
        return mode
    cfg = resolve_llm_config()
    return "openai_compatible" if cfg.ok else "stub"
