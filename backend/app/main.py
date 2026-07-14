from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.account_store import (
    clear_account_auth,
    clear_openvidau_env,
    delete_cloud_session,
    get_cloud_session,
    load_account_auth,
)
from app.attachments import AttachmentError, AttachmentStore
from app.auth import verify_token, verify_token_header_or_query
from app.catalog import get_expert, get_expert_raw, list_experts
from app.config import settings
from app.credentials import set_credential
from app.expert_install import ExpertInstallError, install_expert
from app.llm_config import effective_llm_mode, resolve_llm_config
from app.models import SessionCreateRequest, SessionCreateResponse
from app.openvidau_sso import (
    OpenVidauSsoError,
    create_login_ticket,
    poll_login_ticket,
    try_rebootstrap_on_startup,
)
from app.sessions import (
    PACKAGE_ROOT,
    create_session,
    delete_session,
    get_session,
    get_session_messages,
    get_session_timeline,
    init_db,
    list_sessions,
)
from app.ws import router as ws_router

app = FastAPI(title="Vidau Cloud Agent", version="0.3.0")
app.include_router(ws_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    try:
        try_rebootstrap_on_startup()
    except Exception:
        pass


@app.get("/health")
def health():
    llm = resolve_llm_config()
    auth = load_account_auth()
    account = (auth or {}).get("account") if auth else None
    return {
        "ok": True,
        "mcp_mode": settings.effective_mcp_mode(),
        "mcp_mode_setting": settings.mcp_mode,
        "mcp_transport": settings.mcp_transport,
        "sandbox_provider": settings.sandbox_provider,
        "tiktok_url_configured": bool(settings.mcp_tiktok_url),
        "creative_url_configured": bool(settings.mcp_creative_url),
        "geo_url_configured": bool(settings.mcp_geo_url),
        "llm_mode": effective_llm_mode(),
        "llm_model": llm.model if llm.ok else None,
        "llm_source": llm.source if llm.ok else None,
        "llm_configured": llm.ok,
        "vidau_signed_in": bool(auth),
        "vidau_plan": (account or {}).get("plan") if isinstance(account, dict) else None,
    }


class LoginTicketRequest(BaseModel):
    locale: str | None = None


class LoginTicketPollRequest(BaseModel):
    ticket: str


@app.post("/v1/auth/login-ticket")
def auth_login_ticket(body: LoginTicketRequest | None = None):
    try:
        return create_login_ticket(locale=(body.locale if body else None))
    except OpenVidauSsoError as exc:
        raise HTTPException(status_code=exc.status or 502, detail=str(exc)) from exc


@app.post("/v1/auth/login-ticket/poll")
def auth_login_ticket_poll(body: LoginTicketPollRequest):
    try:
        return poll_login_ticket(body.ticket)
    except OpenVidauSsoError as exc:
        raise HTTPException(status_code=exc.status or 502, detail=str(exc)) from exc


@app.get("/v1/auth/me")
def auth_me(token: str = Depends(verify_token)):
    llm = resolve_llm_config()
    session = get_cloud_session(token)
    auth = load_account_auth()
    user = (auth or {}).get("user") if auth else {}
    account = (auth or {}).get("account") if auth else {}
    if session and session.get("meta"):
        meta = session["meta"]
    else:
        meta = {}
    return {
        "user": user or {"id": (session or {}).get("user_id")},
        "account": account or {"plan": meta.get("plan")},
        "llm": {
            "configured": llm.ok,
            "model": llm.model if llm.ok else None,
            "base_url": llm.base_url if llm.ok else None,
            "source": llm.source if llm.ok else None,
        },
        "session_user_id": (session or {}).get("user_id"),
    }


@app.post("/v1/auth/logout")
def auth_logout(token: str = Depends(verify_token)):
    delete_cloud_session(token)
    # Keep openvidau.env so LLM still works for other sessions on this host;
    # clear only when last session — for P0 clear auth files on logout.
    clear_account_auth()
    clear_openvidau_env()
    return {"ok": True}


@app.get("/v1/experts")
def experts_list(_: str = Depends(verify_token)):
    return list_experts()


@app.get("/v1/experts/{expert_id}")
def expert_detail(expert_id: str, _: str = Depends(verify_token)):
    return get_expert(expert_id)


@app.post("/v1/experts/{expert_id}/install")
def expert_install(expert_id: str, _: str = Depends(verify_token)):
    raw = get_expert_raw(expert_id)
    try:
        result = install_expert(raw)
    except ExpertInstallError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {**result, "expert": get_expert(expert_id)}


class CredentialRequest(BaseModel):
    api_key: str


@app.put("/v1/credentials/{server}")
def put_credentials(
    server: str,
    body: CredentialRequest,
    _: str = Depends(verify_token),
):
    set_credential("default", server, body.api_key)
    return {"ok": True, "server": server}


@app.post("/v1/sessions", response_model=SessionCreateResponse)
def sessions_create(
    body: SessionCreateRequest,
    _: str = Depends(verify_token),
):
    raw = get_expert_raw(body.expert_id)
    if (raw.get("availability") or "ready") == "coming_soon":
        raise HTTPException(
            status_code=403,
            detail="该 Expert 即将支持：需要云端 browser 运行时，暂不可开启会话。",
        )
    return create_session(body.expert_id)


@app.get("/v1/sessions")
def sessions_list(
    expert_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: str = Depends(verify_token),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    items = list_sessions(
        user_id="default",
        expert_id=expert_id,
        limit=limit,
        offset=offset,
    )
    return {"sessions": items}


@app.get("/v1/sessions/{session_id}/messages")
def sessions_messages(session_id: str, _: str = Depends(verify_token)):
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": get_session_messages(session_id)}


@app.get("/v1/sessions/{session_id}/timeline")
def sessions_timeline(session_id: str, _: str = Depends(verify_token)):
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "items": get_session_timeline(session_id)}


@app.delete("/v1/sessions/{session_id}")
def sessions_delete(session_id: str, _: str = Depends(verify_token)):
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


def _attachment_store_root() -> Path:
    return PACKAGE_ROOT / "data" / "sessions"


def get_attachment_store() -> AttachmentStore:
    return AttachmentStore(root=_attachment_store_root())


def _require_session(session_id: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _attachment_preview_prefix(session_id: str) -> str:
    return f"/v1/sessions/{session_id}/attachments"


@app.post("/v1/sessions/{session_id}/attachments")
async def attachments_create(
    session_id: str,
    request: Request,
    _: str = Depends(verify_token),
):
    _require_session(session_id)
    store = get_attachment_store()
    preview_prefix = _attachment_preview_prefix(session_id)
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        body = await request.json()
        if body.get("kind") != "url":
            raise HTTPException(status_code=400, detail="Invalid kind")
        url = body.get("url", "")
        try:
            att = store.add_url(session_id, url)
        except AttachmentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return store.to_public_dict(att)

    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Missing file")
    content = await upload.read()
    filename = upload.filename or "upload"
    mime = upload.content_type or "application/octet-stream"
    try:
        att = store.add_file(
            session_id,
            filename=filename,
            content=content,
            mime=mime,
        )
    except AttachmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return store.to_public_dict(att, preview_path_prefix=preview_prefix)


@app.get("/v1/sessions/{session_id}/attachments")
def attachments_list(
    session_id: str,
    _: str = Depends(verify_token),
):
    _require_session(session_id)
    store = get_attachment_store()
    preview_prefix = _attachment_preview_prefix(session_id)
    attachments = [
        store.to_public_dict(att, preview_path_prefix=preview_prefix)
        for att in store.list(session_id)
    ]
    return {"attachments": attachments}


@app.get("/v1/sessions/{session_id}/attachments/{attachment_id}")
def attachments_get(
    session_id: str,
    attachment_id: str,
    _: str = Depends(verify_token),
):
    """Metadata for a single attachment (avoids 405 when clients omit /file)."""
    _require_session(session_id)
    store = get_attachment_store()
    preview_prefix = _attachment_preview_prefix(session_id)
    try:
        att = store.get(session_id, attachment_id)
    except AttachmentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return store.to_public_dict(att, preview_path_prefix=preview_prefix)


@app.delete("/v1/sessions/{session_id}/attachments/{attachment_id}")
def attachments_delete(
    session_id: str,
    attachment_id: str,
    _: str = Depends(verify_token),
):
    _require_session(session_id)
    store = get_attachment_store()
    try:
        store.delete(session_id, attachment_id)
    except AttachmentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/v1/sessions/{session_id}/attachments/{attachment_id}/file")
def attachments_file(
    session_id: str,
    attachment_id: str,
    _: str = Depends(verify_token_header_or_query),
):
    _require_session(session_id)
    store = get_attachment_store()
    try:
        att = store.get(session_id, attachment_id)
    except AttachmentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if att.kind not in {"image", "video"}:
        raise HTTPException(status_code=404, detail="Not a file attachment")
    path = store.file_path(session_id, attachment_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type=att.mime or "application/octet-stream")
