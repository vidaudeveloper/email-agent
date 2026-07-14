"""OpenVidAU SSO client (login-ticket + bootstrap), aligned with desktop account-auth."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin

import httpx

from app.account_store import (
    create_cloud_session,
    load_account_auth,
    save_account_auth,
    save_openvidau_env,
)
from app.config import settings

DEFAULT_BASE = "https://open.vidau.ai"
ENDPOINTS = {
    "login_ticket": "/sso/auth/login-ticket",
    "login_ticket_poll": "/sso/auth/login-ticket/poll",
    "refresh": "/sso/auth/refresh",
    "bootstrap": "/sso/account/openvidau/bootstrap",
}


class OpenVidauSsoError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def _base_url() -> str:
    return (settings.openvidau_base_url or DEFAULT_BASE).rstrip("/")


def _client_payload(locale: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "client": {
            "app": settings.openvidau_client_app or "vidau-mobile",
            "platform": "mobile",
        }
    }
    if locale:
        body["locale"] = locale
    return body


def _build_login_url(base: str, ticket: str, client_app: str) -> str:
    query = urlencode({"login_ticket": ticket, "client": client_app})
    return f"{base.rstrip('/')}/login?{query}"


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    access_token: str | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    url = urljoin(_base_url() + "/", path.lstrip("/"))
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        res = client.request(method, url, headers=headers, json=body)
    try:
        data = res.json() if res.content else {}
    except Exception:
        data = {}
    if res.status_code >= 400:
        msg = ""
        if isinstance(data, dict):
            msg = str(data.get("message") or data.get("detail") or data.get("error") or "")
        raise OpenVidauSsoError(
            msg or f"SSO error {res.status_code} for {path}",
            status=res.status_code,
        )
    if not isinstance(data, dict):
        return {}
    return data


def create_login_ticket(locale: str | None = None) -> dict[str, Any]:
    """Create SSO login ticket; fallback client app to vidau-desktop if needed."""
    clients = [
        settings.openvidau_client_app or "vidau-mobile",
        "vidau-desktop",
    ]
    # dedupe
    seen: set[str] = set()
    ordered = []
    for c in clients:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    last_error: Exception | None = None
    for app_name in ordered:
        body = {
            "client": {"app": app_name, "platform": "mobile"},
        }
        if locale:
            body["locale"] = locale
        try:
            result = _request("POST", ENDPOINTS["login_ticket"], body=body)
        except OpenVidauSsoError as exc:
            last_error = exc
            continue

        ticket = str(
            result.get("ticket") or result.get("login_ticket") or result.get("id") or ""
        ).strip()
        if not ticket:
            last_error = OpenVidauSsoError("Account API did not return a login ticket.")
            continue

        raw_login = str(
            result.get("login_url") or result.get("redirect_url") or result.get("url") or ""
        ).strip()
        login_url = raw_login or _build_login_url(_base_url(), ticket, app_name)
        poll_ms = result.get("poll_interval_ms")
        try:
            poll_interval_ms = max(500, int(poll_ms)) if poll_ms is not None else 1500
        except (TypeError, ValueError):
            poll_interval_ms = 1500
        expires_in = result.get("expires_in")
        try:
            expires_in_i = int(expires_in) if expires_in is not None else 300
        except (TypeError, ValueError):
            expires_in_i = 300

        return {
            "ticket": ticket,
            "login_url": login_url,
            "poll_interval_ms": poll_interval_ms,
            "expires_in": expires_in_i,
            "client_app": app_name,
        }

    raise OpenVidauSsoError(str(last_error) if last_error else "Failed to create login ticket")


def _extract_tokens(payload: dict[str, Any]) -> tuple[str, str] | None:
    access = str(payload.get("access_token") or "").strip()
    refresh = str(payload.get("refresh_token") or "").strip()
    if access and refresh:
        return access, refresh
    return None


def poll_login_ticket(ticket: str) -> dict[str, Any]:
    """Poll ticket. On success: bootstrap key, issue cloud session_token."""
    ticket = ticket.strip()
    if not ticket:
        raise OpenVidauSsoError("Login ticket is required.")

    result = _request("POST", ENDPOINTS["login_ticket_poll"], body={"ticket": ticket})
    session_payload = result.get("session") if isinstance(result.get("session"), dict) else result
    tokens = _extract_tokens(session_payload if isinstance(session_payload, dict) else {})

    if not tokens:
        status = str(result.get("status") or "pending").lower()
        if status in {"expired", "cancelled", "failed"}:
            return {"status": status}
        return {"status": "pending", "expires_in": result.get("expires_in")}

    access_token, refresh_token = tokens
    user = session_payload.get("user") if isinstance(session_payload, dict) else None
    account = session_payload.get("account") if isinstance(session_payload, dict) else None
    if not isinstance(user, dict):
        user = {}
    if not isinstance(account, dict):
        account = {}

    save_account_auth(
        refresh_token=refresh_token,
        access_token=access_token,
        user=user,
        account=account,
        base_url=_base_url(),
    )

    bootstrap = bootstrap_with_access_token(access_token)
    provider = bootstrap.get("provider") or {}
    api_key = str(provider.get("api_key") or "").strip()
    if not api_key:
        plan = (account or {}).get("plan") or (bootstrap.get("account") or {}).get("plan")
        raise OpenVidauSsoError(
            f"账号未返回可用 OpenVidAU API Key（plan={plan or 'unknown'}）。请确认已购买/开通。"
        )

    base_url = str(provider.get("base_url") or "").strip() or f"{_base_url()}/v1"
    default_model = str(provider.get("default_model") or "").strip() or "gpt-4o-mini"
    vidau_user_id = str(bootstrap.get("vidau_user_id") or user.get("id") or "").strip()

    save_openvidau_env(
        api_key=api_key,
        base_url=base_url,
        user_id=vidau_user_id,
        default_model=default_model,
    )

    user_id = str(user.get("id") or vidau_user_id or "vidau-user")
    session_token = create_cloud_session(
        user_id,
        meta={
            "email": user.get("email"),
            "plan": (bootstrap.get("account") or account or {}).get("plan"),
            "model": default_model,
        },
    )

    acct = bootstrap.get("account") or account or {}
    return {
        "status": "signed_in",
        "session_token": session_token,
        "user": {
            "id": user_id,
            "email": user.get("email") or "",
            "name": user.get("name") or "",
        },
        "account": {
            "plan": acct.get("plan") or "",
            "status": acct.get("status") or "",
        },
        "llm": {
            "configured": True,
            "model": default_model,
            "base_url": base_url.rstrip("/"),
            "source": "sso:bootstrap",
        },
    }


def bootstrap_with_access_token(access_token: str) -> dict[str, Any]:
    return _request(
        "GET",
        ENDPOINTS["bootstrap"],
        access_token=access_token,
    )


def refresh_access_token() -> str | None:
    stored = load_account_auth()
    if not stored:
        return None
    refresh = str(stored.get("refresh_token") or "")
    if not refresh:
        return None
    try:
        result = _request("POST", ENDPOINTS["refresh"], body={"refresh_token": refresh})
    except OpenVidauSsoError:
        return None
    tokens = _extract_tokens(result)
    if not tokens:
        return None
    access, new_refresh = tokens
    save_account_auth(
        refresh_token=new_refresh,
        access_token=access,
        user=stored.get("user") if isinstance(stored.get("user"), dict) else {},
        account=stored.get("account") if isinstance(stored.get("account"), dict) else {},
        base_url=str(stored.get("base_url") or _base_url()),
    )
    return access


def try_rebootstrap_on_startup() -> bool:
    """Best-effort: refresh + bootstrap into openvidau.env. Returns True if LLM key ready."""
    access = refresh_access_token()
    if not access:
        stored = load_account_auth()
        access = str((stored or {}).get("access_token") or "") or None
    if not access:
        return False
    try:
        bootstrap = bootstrap_with_access_token(access)
    except OpenVidauSsoError:
        return False
    provider = bootstrap.get("provider") or {}
    api_key = str(provider.get("api_key") or "").strip()
    if not api_key:
        return False
    base_url = str(provider.get("base_url") or "").strip() or f"{_base_url()}/v1"
    default_model = str(provider.get("default_model") or "").strip() or "gpt-4o-mini"
    save_openvidau_env(
        api_key=api_key,
        base_url=base_url,
        user_id=str(bootstrap.get("vidau_user_id") or ""),
        default_model=default_model,
    )
    return True
