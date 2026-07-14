"""Creative attachment URL bridge tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.attachments import AttachmentStore
from app.creative_bridge import (
    CreativeBridgeError,
    apply_creative_reference_urls,
    expert_needs_creative_bridge,
    needs_creative_reference_bridge,
    resolve_creative_reference_urls,
)


def fake_att(**fields):
    base = {
        "id": "att_test",
        "kind": "image",
        "label": "ref.jpg",
        "ref": "@image:att_test",
        "mime": "image/jpeg",
    }
    base.update(fields)
    return base


class FakeGw:
    def __init__(
        self,
        *,
        instructions: dict | None = None,
        upload_reference: dict | None = None,
        instructions_fail: bool = False,
    ):
        self.calls: list[tuple[str, str, dict]] = []
        self.instructions_fail = instructions_fail
        self.instructions = instructions or {
            "ok": True,
            "result": {
                "upload": {
                    "put_url": "https://s3.example/put",
                    "file_url": "https://cdn.example/uploaded.jpg",
                    "content_type": "image/jpeg",
                }
            },
        }
        self.upload_reference = upload_reference or {
            "ok": True,
            "result": {"file_url": "https://cdn.example/fallback.jpg"},
        }

    async def call_tool(self, server: str, tool: str, arguments: dict):
        self.calls.append((server, tool, arguments))
        if tool == "creative_get_upload_instructions":
            if self.instructions_fail:
                return {"ok": False, "error": "instructions unavailable"}
            return self.instructions
        if tool == "creative_upload_reference":
            return self.upload_reference
        raise AssertionError(f"unexpected tool {tool}")


@pytest.mark.asyncio
async def test_bridge_uses_existing_https():
    urls = await resolve_creative_reference_urls(
        session_id="s1",
        attachments=[fake_att(kind="url", url="https://cdn.example/a.png")],
        gateway=FakeGw(),
        store=AttachmentStore(root=Path("/tmp/unused")),
    )
    assert urls == ["https://cdn.example/a.png"]


@pytest.mark.asyncio
async def test_bridge_uploads_local_via_instructions(tmp_path: Path, monkeypatch):
    store = AttachmentStore(root=tmp_path)
    data = b"fake-image-bytes"
    att = store.add_file("s1", filename="ref.jpg", content=data, mime="image/jpeg")
    public = store.to_public_dict(
        att, preview_path_prefix="/v1/sessions/s1/attachments"
    )

    put_calls: list[tuple[str, bytes, str | None]] = []

    async def fake_put(url: str, *, content: bytes, content_type: str | None):
        put_calls.append((url, content, content_type))

    monkeypatch.setattr("app.creative_bridge._http_put", fake_put)

    gw = FakeGw()
    urls = await resolve_creative_reference_urls(
        session_id="s1",
        attachments=[public],
        gateway=gw,
        store=store,
    )

    assert urls == ["https://cdn.example/uploaded.jpg"]
    assert gw.calls[0][0:2] == ("creative-agent", "creative_get_upload_instructions")
    assert put_calls == [
        ("https://s3.example/put", data, "image/jpeg"),
    ]


@pytest.mark.asyncio
async def test_bridge_reuploads_local_agent_https_url(tmp_path: Path, monkeypatch):
    store = AttachmentStore(root=tmp_path)
    data = b"img"
    att = store.add_file("s1", filename="ref.jpg", content=data, mime="image/jpeg")
    public = store.to_public_dict(
        att, preview_path_prefix="/v1/sessions/s1/attachments"
    )
    public["url"] = "http://127.0.0.1:8787/v1/sessions/s1/attachments/att/file"

    async def fake_put(url: str, *, content: bytes, content_type: str | None):
        pass

    monkeypatch.setattr("app.creative_bridge._http_put", fake_put)

    gw = FakeGw()
    urls = await resolve_creative_reference_urls(
        session_id="s1",
        attachments=[public],
        gateway=gw,
        store=store,
        public_base_url="http://127.0.0.1:8787",
    )

    assert urls == ["https://cdn.example/uploaded.jpg"]
    assert gw.calls[0][1] == "creative_get_upload_instructions"


@pytest.mark.asyncio
async def test_bridge_falls_back_to_upload_reference(tmp_path: Path, monkeypatch):
    store = AttachmentStore(root=tmp_path)
    data = b"tiny"
    att = store.add_file("s1", filename="ref.jpg", content=data, mime="image/jpeg")
    public = store.to_public_dict(att)

    async def fake_put(url: str, *, content: bytes, content_type: str | None):
        raise RuntimeError("should not PUT when instructions fail")

    monkeypatch.setattr("app.creative_bridge._http_put", fake_put)

    gw = FakeGw(instructions_fail=True)
    urls = await resolve_creative_reference_urls(
        session_id="s1",
        attachments=[public],
        gateway=gw,
        store=store,
    )

    assert urls == ["https://cdn.example/fallback.jpg"]
    assert [call[1] for call in gw.calls] == [
        "creative_get_upload_instructions",
        "creative_upload_reference",
    ]
    assert "content_base64" in gw.calls[1][2]


@pytest.mark.asyncio
async def test_bridge_raises_when_all_paths_fail(tmp_path: Path, monkeypatch):
    store = AttachmentStore(root=tmp_path)
    att = store.add_file("s1", filename="ref.jpg", content=b"x", mime="image/jpeg")
    public = store.to_public_dict(att)

    gw = FakeGw(
        instructions_fail=True,
        upload_reference={"ok": False, "error": "fallback failed"},
    )

    with pytest.raises(CreativeBridgeError, match="Creative reference upload failed"):
        await resolve_creative_reference_urls(
            session_id="s1",
            attachments=[public],
            gateway=gw,
            store=store,
        )


def test_apply_creative_reference_urls_merges_when_empty():
    args = apply_creative_reference_urls(
        "mcp_creative_agent_creative_generate_image",
        {"prompt": "a cat"},
        ["https://cdn.example/a.png"],
    )
    assert args["reference_urls"] == ["https://cdn.example/a.png"]
    assert args["prompt"] == "a cat"


def test_apply_creative_reference_urls_preserves_existing():
    args = apply_creative_reference_urls(
        "mcp_creative_agent_creative_image_to_video",
        {"reference_image_urls": ["https://cdn.example/existing.png"]},
        ["https://cdn.example/new.png"],
    )
    assert args["reference_image_urls"] == ["https://cdn.example/existing.png"]


def test_expert_and_tool_gates():
    assert expert_needs_creative_bridge({"requires_mcp": ["creative-agent"]})
    assert not expert_needs_creative_bridge({"requires_mcp": ["tiktok-ads-agent"]})
    assert needs_creative_reference_bridge("mcp_creative_agent_creative_generate_image")
    assert not needs_creative_reference_bridge("mcp_creative_agent_creative_get_job")
    assert not needs_creative_reference_bridge(
        "mcp_creative_agent_creative_generate_script"
    )
