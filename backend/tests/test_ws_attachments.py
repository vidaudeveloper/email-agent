"""WS chat.send attachment_ids and chat.user attachments."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.agent_loop import build_attachment_context, enrich_user_content
from app.attachments import AttachmentStore
from app.main import app

AUTH = {"Authorization": "Bearer dev-local-token"}
client = TestClient(app)


def _create_session() -> str:
    response = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "tiktok-ads-agent"},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


def test_build_attachment_context_formats_lines():
    attachments = [
        {
            "id": "att_01",
            "kind": "image",
            "ref": "@image:att_01",
            "mime": "image/jpeg",
            "url": "/v1/sessions/s1/attachments/att_01/file",
        },
        {
            "id": "att_02",
            "kind": "url",
            "ref": "@url:att_02",
            "url": "https://example.com/ref.png",
        },
    ]
    block = build_attachment_context(attachments)
    assert block.startswith("[Attachments]")
    assert (
        "@image:att_01 image/jpeg "
        "url=http://127.0.0.1:8787/v1/sessions/s1/attachments/att_01/file"
    ) in block
    assert "@url:att_02 url url=https://example.com/ref.png" in block


def test_enrich_user_content_appends_block():
    attachments = [
        {
            "ref": "@image:att_01",
            "mime": "image/jpeg",
            "url": "/v1/sessions/s1/attachments/att_01/file",
        }
    ]
    enriched = enrich_user_content("optimize this", attachments)
    assert enriched.startswith("optimize this")
    assert "[Attachments]" in enriched


def test_enrich_user_content_attachments_only():
    attachments = [
        {
            "ref": "@url:att_01",
            "kind": "url",
            "url": "https://example.com/a.jpg",
        }
    ]
    enriched = enrich_user_content("", attachments)
    assert enriched.startswith("[Attachments]")
    assert "https://example.com/a.jpg" in enriched


def test_ws_send_with_attachments_only(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    monkeypatch.setattr(
        "app.ws._get_attachment_store",
        lambda: AttachmentStore(root=tmp_path),
    )

    session_id = _create_session()
    upload = client.post(
        f"/v1/sessions/{session_id}/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "https://example.com/ref.jpg"},
    )
    assert upload.status_code == 200
    att_id = upload.json()["id"]

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws?token=dev-local-token"
    ) as ws:
        ws.send_json(
            {
                "type": "chat.send",
                "content": "",
                "attachment_ids": [att_id],
            }
        )

        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] == "chat.done":
                break

    chat_user = next(e for e in events if e["type"] == "chat.user")
    assert chat_user["content"] == ""
    assert len(chat_user["attachments"]) == 1
    assert chat_user["attachments"][0]["id"] == att_id
    assert chat_user["attachments"][0]["kind"] == "url"


def test_ws_send_with_content_and_attachments(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    monkeypatch.setattr(
        "app.ws._get_attachment_store",
        lambda: AttachmentStore(root=tmp_path),
    )

    session_id = _create_session()
    data = b"\xff\xd8\xff" + b"0" * 50
    upload = client.post(
        f"/v1/sessions/{session_id}/attachments",
        headers=AUTH,
        files={"file": ("pic.jpg", data, "image/jpeg")},
    )
    assert upload.status_code == 200
    att_id = upload.json()["id"]

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws?token=dev-local-token"
    ) as ws:
        ws.send_json(
            {
                "type": "chat.send",
                "content": "use this image",
                "attachment_ids": [att_id],
            }
        )

        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] == "chat.done":
                break

    chat_user = next(e for e in events if e["type"] == "chat.user")
    assert chat_user["content"] == "use this image"
    assert chat_user["attachments"][0]["kind"] == "image"
    assert chat_user["attachments"][0]["preview_url"] == (
        f"/v1/sessions/{session_id}/attachments/{att_id}/file"
    )


def test_ws_rejects_missing_content_and_attachments(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    session_id = _create_session()

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws?token=dev-local-token"
    ) as ws:
        ws.send_json({"type": "chat.send", "content": "", "attachment_ids": []})
        event = ws.receive_json()

    assert event["type"] == "chat.error"
    assert event["content"] == "Missing content"


def test_ws_rejects_unknown_attachment_id(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    monkeypatch.setattr(
        "app.ws._get_attachment_store",
        lambda: AttachmentStore(root=tmp_path),
    )

    session_id = _create_session()

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws?token=dev-local-token"
    ) as ws:
        ws.send_json(
            {
                "type": "chat.send",
                "content": "hello",
                "attachment_ids": ["att_missing"],
            }
        )
        event = ws.receive_json()

    assert event["type"] == "chat.error"
    assert "Attachment not found" in event["content"]


def test_ws_rejects_invalid_attachment_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    session_id = _create_session()

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws?token=dev-local-token"
    ) as ws:
        ws.send_json(
            {
                "type": "chat.send",
                "content": "hello",
                "attachment_ids": "att_01",
            }
        )
        event = ws.receive_json()

    assert event["type"] == "chat.error"
    assert event["content"] == "Invalid attachment_ids"
