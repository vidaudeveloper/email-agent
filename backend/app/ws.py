from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.attachments import AttachmentError, AttachmentStore
from app.auth import is_valid_token
from app.media_hub import media_hub
from app.runtime import stream_user_message
from app.sessions import PACKAGE_ROOT, get_session, persist_timeline_event


def _get_attachment_store() -> AttachmentStore:
    return AttachmentStore(root=PACKAGE_ROOT / "data" / "sessions")

router = APIRouter()


@router.websocket("/v1/sessions/{session_id}/ws")
async def session_ws(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    if not is_valid_token(websocket, token):
        await websocket.close(code=1008, reason="Invalid token")
        return

    if get_session(session_id) is None:
        await websocket.close(code=1008, reason="Session not found")
        return

    await websocket.accept()

    outbound: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _emit(event: dict) -> None:
        persist_timeline_event(event)
        await outbound.put(event)

    async def _pump() -> None:
        while True:
            item = await outbound.get()
            if item is None:
                return
            try:
                await websocket.send_json(item)
            except Exception:
                return

    await media_hub.bind(session_id, _emit)
    pump_task = asyncio.create_task(_pump())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await outbound.put(
                    {
                        "type": "chat.error",
                        "session_id": session_id,
                        "content": "Invalid JSON",
                    }
                )
                continue

            event_type = data.get("type")
            if event_type != "chat.send":
                await outbound.put(
                    {
                        "type": "chat.error",
                        "session_id": session_id,
                        "content": f"Unknown event type: {event_type}",
                    }
                )
                continue

            content = (data.get("content") or "").strip()
            raw_ids = data.get("attachment_ids")
            if raw_ids is None:
                attachment_ids: list = []
            elif not isinstance(raw_ids, list) or any(
                not isinstance(item, str) or not item.strip() for item in raw_ids
            ):
                await outbound.put(
                    {
                        "type": "chat.error",
                        "session_id": session_id,
                        "content": "Invalid attachment_ids",
                    }
                )
                continue
            else:
                attachment_ids = raw_ids
            if not content and not attachment_ids:
                await outbound.put(
                    {
                        "type": "chat.error",
                        "session_id": session_id,
                        "content": "Missing content",
                    }
                )
                continue

            store = _get_attachment_store()
            preview_prefix = f"/v1/sessions/{session_id}/attachments"
            try:
                atts = store.resolve_many(session_id, attachment_ids)
            except AttachmentError as exc:
                await outbound.put(
                    {
                        "type": "chat.error",
                        "session_id": session_id,
                        "content": str(exc),
                    }
                )
                continue

            public_attachments = [
                store.to_public_dict(a, preview_path_prefix=preview_prefix) for a in atts
            ]

            try:
                async for event in stream_user_message(
                    session_id,
                    content,
                    attachments=public_attachments,
                ):
                    await _emit(event)
            except (ValueError, AttachmentError) as exc:
                await outbound.put(
                    {
                        "type": "chat.error",
                        "session_id": session_id,
                        "content": str(exc),
                    }
                )
            except Exception as exc:
                await outbound.put(
                    {
                        "type": "chat.assistant",
                        "session_id": session_id,
                        "content": f"执行失败：{exc}",
                    }
                )
                await outbound.put(
                    {
                        "type": "chat.done",
                        "session_id": session_id,
                    }
                )
    except WebSocketDisconnect:
        return
    finally:
        await media_hub.unbind(session_id)
        await outbound.put(None)
        try:
            await asyncio.wait_for(pump_task, timeout=2.0)
        except Exception:
            pump_task.cancel()
