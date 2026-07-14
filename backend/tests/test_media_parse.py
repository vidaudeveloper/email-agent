"""Unit tests for media_parse."""

from app.media_parse import classify_media_tool, normalize_tool_suffix, parse_media_result


def test_normalize_tool_suffix():
    assert (
        normalize_tool_suffix("mcp_creative_agent_creative_generate_image")
        == "creative_generate_image"
    )
    assert (
        normalize_tool_suffix("mcp_creative-agent_creative_generate_image")
        == "creative_generate_image"
    )


def test_classify_sync_image():
    info = classify_media_tool(
        "mcp_creative_agent_creative_generate_image",
        {"aspect_ratio": "9:16"},
    )
    assert info is not None
    assert info.mode == "sync"
    assert info.kind == "image"
    assert info.ratio == "9:16"


def test_classify_non_media():
    info = classify_media_tool("mcp_creative_agent_creative_get_job", {})
    assert info is not None
    assert info.mode == "none"


def test_parse_sync_image_result():
    payload = {
        "ok": True,
        "result": {
            "status": "completed",
            "artifacts": [
                {
                    "type": "image",
                    "urls": {
                        "download": "https://example.com/a.jpg",
                        "preview": "https://example.com/a.jpg",
                    },
                }
            ],
            "tracking": {"mode": "sync", "user_message": "图片生成完成"},
        },
    }
    parsed = parse_media_result(payload, fallback_job_id="local-1", default_kind="image")
    assert parsed.urls[0].endswith("a.jpg")
    assert parsed.should_poll is False
    assert parsed.message == "图片生成完成"


def test_parse_async_job():
    payload = {
        "ok": True,
        "result": {
            "job_id": "job-123",
            "status": "queued",
            "tracking": {"should_continue_polling": True, "user_message": "已提交"},
        },
    }
    parsed = parse_media_result(payload, fallback_job_id="local-1", default_kind="video")
    assert parsed.job_id == "job-123"
    assert parsed.should_poll is True
