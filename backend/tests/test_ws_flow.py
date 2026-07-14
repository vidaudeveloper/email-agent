import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-token"}


def _create_session() -> str:
    response = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "tiktok-ads-agent"},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


def test_ws_without_llm_reports_clear_error():
    """conftest forces llm_mode=stub — must not silently mock-succeed."""
    session_id = _create_session()

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws?token=dev-local-token"
    ) as ws:
        ws.send_json(
            {"type": "chat.send", "content": "帮我创建一个测试广告系列"}
        )

        events = []
        while True:
            event = ws.receive_json()
            assert event["session_id"] == session_id
            events.append(event)
            if event["type"] == "chat.done":
                break

    types = [e["type"] for e in events]
    assert types[0] == "sandbox.status"
    assert "chat.user" in types
    assert "chat.assistant" in types
    assert types[-1] == "chat.done"
    assistant = next(e for e in events if e["type"] == "chat.assistant")
    assert "LLM" in assistant["content"] or "未配置" in assistant["content"]
    # Must not look like the old keyword stub success
    assert "Mock create_campaign succeeded" not in assistant["content"]


def test_ws_auth_via_header():
    session_id = _create_session()

    with client.websocket_connect(
        f"/v1/sessions/{session_id}/ws",
        headers=AUTH,
    ) as ws:
        ws.send_json({"type": "chat.send", "content": "hello"})
        received_types = []
        while True:
            event = ws.receive_json()
            received_types.append(event["type"])
            if event["type"] == "chat.done":
                break

    assert received_types[-1] == "chat.done"


def test_ws_rejects_invalid_token():
    session_id = _create_session()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/v1/sessions/{session_id}/ws?token=bad-token"
        ):
            pass

    assert exc_info.value.code == 1008


def test_ws_rejects_unknown_session():
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/v1/sessions/00000000-0000-0000-0000-000000000000/ws?token=dev-local-token"
        ):
            pass

    assert exc_info.value.code == 1008
