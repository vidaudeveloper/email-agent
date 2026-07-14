from app.sessions import (
    add_message,
    create_session,
    get_session_timeline,
    init_db,
    persist_timeline_event,
)


def test_persist_steps_and_media_timeline(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUD_AGENT_SQLITE_PATH", str(tmp_path / "t.db"))
    # settings may already be loaded — force path via settings if available
    from app import config

    monkeypatch.setattr(config.settings, "sqlite_path", str(tmp_path / "t.db"))
    init_db()
    created = create_session("vidau-creative-agent-oneclick")
    sid = created.session_id

    add_message(sid, "user", "生成一张图")
    persist_timeline_event(
        {"type": "tool.mcp", "session_id": sid, "tool": "creative_generate_image", "phase": "start"}
    )
    persist_timeline_event(
        {
            "type": "media.placeholder",
            "session_id": sid,
            "job_id": "job-1",
            "kind": "image",
            "ratio": "1:1",
            "label": "生成图片",
        }
    )
    persist_timeline_event(
        {
            "type": "media.ready",
            "session_id": sid,
            "job_id": "job-1",
            "kind": "image",
            "urls": ["https://example.com/a.png"],
        }
    )
    persist_timeline_event(
        {"type": "tool.mcp", "session_id": sid, "tool": "creative_generate_image", "phase": "end"}
    )
    add_message(sid, "assistant", "已完成")

    items = get_session_timeline(sid)
    types = [i["type"] for i in items]
    assert "message" in types
    assert "steps" in types
    assert "media" in types
    media = next(i for i in items if i["type"] == "media")
    assert media["state"] == "ready"
    assert media["urls"] == ["https://example.com/a.png"]
    steps = next(i for i in items if i["type"] == "steps")
    assert steps["collapsed_default"] is True
    assert steps["steps"][0]["status"] == "done"
