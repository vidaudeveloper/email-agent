from pathlib import Path

from fastapi.testclient import TestClient

from app import sessions as sessions_mod
from app.main import app

AUTH = {"Authorization": "Bearer dev-local-token"}


def test_create_sets_updated_at(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    created = sessions_mod.create_session("vidau-creative-agent-oneclick")
    row = sessions_mod.get_session(created.session_id)
    assert row is not None
    assert row.get("updated_at")
    assert row["updated_at"] == row["created_at"]


def test_add_message_bumps_updated_at(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    created = sessions_mod.create_session("vidau-creative-agent-oneclick")
    sid = created.session_id
    before = sessions_mod.get_session(sid)["updated_at"]
    sessions_mod.add_message(sid, "user", "hello")
    after = sessions_mod.get_session(sid)["updated_at"]
    assert after >= before
    msgs = sessions_mod.get_session_messages(sid)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "id" in msgs[0]


def test_list_sessions_order_and_preview(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    a = sessions_mod.create_session("vidau-creative-agent-oneclick")
    b = sessions_mod.create_session("tiktok-ads-agent")
    sessions_mod.add_message(a.session_id, "user", "first")
    sessions_mod.add_message(b.session_id, "assistant", "second reply")
    listed = sessions_mod.list_sessions(user_id="default", limit=50, offset=0)
    assert len(listed) >= 2
    assert listed[0]["session_id"] == b.session_id
    assert "second" in listed[0]["preview"]
    assert listed[0]["message_count"] >= 1


def test_delete_session_removes_messages(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    created = sessions_mod.create_session("vidau-creative-agent-oneclick")
    sid = created.session_id
    sessions_mod.add_message(sid, "user", "bye")
    assert sessions_mod.delete_session(sid) is True
    assert sessions_mod.get_session(sid) is None
    assert sessions_mod.get_session_messages(sid) == []
    assert sessions_mod.delete_session(sid) is False


def test_http_list_messages_delete(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "api.db"))
    sessions_mod.init_db()
    client = TestClient(app)
    sid = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "vidau-creative-agent-oneclick"},
    ).json()["session_id"]
    sessions_mod.add_message(sid, "user", "hi there")
    listed = client.get("/v1/sessions", headers=AUTH)
    assert listed.status_code == 200
    assert any(s["session_id"] == sid for s in listed.json()["sessions"])
    msgs = client.get(f"/v1/sessions/{sid}/messages", headers=AUTH)
    assert msgs.status_code == 200
    assert msgs.json()["messages"][0]["content"] == "hi there"
    deleted = client.delete(f"/v1/sessions/{sid}", headers=AUTH)
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get(f"/v1/sessions/{sid}/messages", headers=AUTH).status_code == 404


def test_http_unauthorized(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "api.db"))
    sessions_mod.init_db()
    client = TestClient(app)
    assert client.get("/v1/sessions").status_code == 401


def test_http_messages_unknown_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "api.db"))
    sessions_mod.init_db()
    client = TestClient(app)
    r = client.get("/v1/sessions/nonexistent-session/messages", headers=AUTH)
    assert r.status_code == 404
