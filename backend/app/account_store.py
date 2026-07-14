"""Persist OpenVidAU SSO session, API key env, and Cloud Agent session tokens."""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PACKAGE_ROOT / "data"
ACCOUNT_AUTH_FILE = DATA_DIR / "account_auth.json"
OPENVIDAU_ENV_FILE = DATA_DIR / "openvidau.env"
CLOUD_SESSIONS_FILE = DATA_DIR / "cloud_sessions.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def save_account_auth(
    *,
    refresh_token: str,
    access_token: str,
    user: dict[str, Any] | None,
    account: dict[str, Any] | None,
    base_url: str,
) -> None:
    _write_json(
        ACCOUNT_AUTH_FILE,
        {
            "schema_version": 1,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "user": user or {},
            "account": account or {},
            "base_url": base_url,
            "updated_at": _now_iso(),
        },
    )


def load_account_auth() -> dict[str, Any] | None:
    data = _read_json(ACCOUNT_AUTH_FILE, None)
    if not isinstance(data, dict) or not data.get("refresh_token"):
        return None
    return data


def clear_account_auth() -> None:
    if ACCOUNT_AUTH_FILE.exists():
        ACCOUNT_AUTH_FILE.unlink()


def save_openvidau_env(
    *,
    api_key: str,
    base_url: str,
    user_id: str = "",
    default_model: str = "",
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"OPENVIDAU_API_KEY={api_key}",
        f"OPENVIDAU_BASE_URL={base_url.rstrip('/')}",
    ]
    if user_id:
        lines.append(f"VIDAU_USER_ID={user_id}")
    if default_model:
        lines.append(f"OPENVIDAU_DEFAULT_MODEL={default_model}")
    OPENVIDAU_ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(OPENVIDAU_ENV_FILE, 0o600)
    except OSError:
        pass


def load_openvidau_env() -> dict[str, str]:
    if not OPENVIDAU_ENV_FILE.exists():
        return {}
    out: dict[str, str] = {}
    for line in OPENVIDAU_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def clear_openvidau_env() -> None:
    if OPENVIDAU_ENV_FILE.exists():
        OPENVIDAU_ENV_FILE.unlink()


def create_cloud_session(user_id: str, meta: dict[str, Any] | None = None) -> str:
    token = secrets.token_urlsafe(32)
    data = _read_json(CLOUD_SESSIONS_FILE, {"sessions": {}})
    sessions = data.setdefault("sessions", {})
    sessions[token] = {
        "user_id": user_id,
        "created_at": _now_iso(),
        "meta": meta or {},
    }
    _write_json(CLOUD_SESSIONS_FILE, data)
    return token


def get_cloud_session(token: str) -> dict[str, Any] | None:
    data = _read_json(CLOUD_SESSIONS_FILE, {"sessions": {}})
    return (data.get("sessions") or {}).get(token)


def delete_cloud_session(token: str) -> None:
    data = _read_json(CLOUD_SESSIONS_FILE, {"sessions": {}})
    sessions = data.get("sessions") or {}
    if token in sessions:
        del sessions[token]
        _write_json(CLOUD_SESSIONS_FILE, data)


def clear_all_cloud_sessions() -> None:
    _write_json(CLOUD_SESSIONS_FILE, {"sessions": {}})


def new_pending_ticket_id() -> str:
    return str(uuid.uuid4())
