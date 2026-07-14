from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.account_store import get_cloud_session
from app.config import settings

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


def _token_ok(token: str) -> bool:
    if not token:
        return False
    if settings.allow_dev_token and token == settings.dev_token:
        return True
    return get_cloud_session(token) is not None


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    if not _token_ok(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def verify_token_header_or_query(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    token: str | None = Query(None, description="Bearer token for media preload"),
) -> str:
    """Accept Authorization header or ?token= (for Image.network / <img>)."""
    candidates: list[str] = []
    if credentials and credentials.credentials:
        candidates.append(credentials.credentials)
    if token:
        candidates.append(token)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        candidates.append(auth[7:].strip())
    for candidate in candidates:
        if _token_ok(candidate):
            return candidate
    raise HTTPException(status_code=401, detail="Invalid token")


def is_valid_token(websocket: WebSocket, token: Optional[str] = None) -> bool:
    candidates: list[str] = []
    if token:
        candidates.append(token)

    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        candidates.append(auth[7:])

    return any(_token_ok(c) for c in candidates)
