"""Bridge session attachments to Creative MCP HTTPS reference URLs."""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.attachments import AttachmentStore
from app.config import settings
from app.media_parse import normalize_tool_suffix

CREATIVE_SERVER = "creative-agent"
UPLOAD_INSTRUCTIONS_TOOL = "creative_get_upload_instructions"
UPLOAD_REFERENCE_TOOL = "creative_upload_reference"

# Tools that accept reference URLs from session attachments.
_REFERENCE_ARG_BY_TOOL: dict[str, str] = {
    "creative_generate_image": "reference_urls",
    "creative_image_to_video": "reference_image_urls",
    "creative_first_frame_to_video": "reference_image_urls",
    "creative_generate_video": "reference_image_urls",
    "creative_submit_workflow": "reference_urls",
    "creative_submit_script2film": "reference_urls",
    "creative_submit_script2film_keyframes": "reference_urls",
    "creative_submit_batch_variants": "reference_urls",
}

# Max bytes for base64 fallback (align with small-image guidance in creative-platform).
_BASE64_FALLBACK_MAX_BYTES = 5 * 1024 * 1024


class CreativeBridgeError(Exception):
    """Failed to resolve one or more attachments for Creative MCP."""


def expert_needs_creative_bridge(expert: dict[str, Any]) -> bool:
    requires = expert.get("requires_mcp") or []
    return CREATIVE_SERVER in requires


def needs_creative_reference_bridge(tool_name: str) -> bool:
    suffix = normalize_tool_suffix(tool_name)
    return suffix in _REFERENCE_ARG_BY_TOOL


def reference_arg_key(tool_name: str) -> str | None:
    suffix = normalize_tool_suffix(tool_name)
    return _REFERENCE_ARG_BY_TOOL.get(suffix)


def apply_creative_reference_urls(
    tool_name: str,
    args: dict[str, Any],
    resolved_urls: list[str],
) -> dict[str, Any]:
    """Fill reference URL args only when missing or empty."""
    if not resolved_urls:
        return args
    key = reference_arg_key(tool_name)
    if not key:
        return args
    merged = dict(args)
    existing = merged.get(key)
    if existing is None or existing == [] or existing == "":
        merged[key] = list(resolved_urls)
    return merged


def _local_agent_netlocs(public_base_url: str) -> set[str]:
    base = (public_base_url or settings.public_base_url or "").strip()
    netlocs: set[str] = {"127.0.0.1", "localhost", "0.0.0.0"}
    if base:
        parsed = urlparse(base if "://" in base else f"http://{base}")
        if parsed.netloc:
            netlocs.add(parsed.netloc.lower())
            host = parsed.hostname
            if host:
                netlocs.add(host.lower())
                if parsed.port:
                    netlocs.add(f"{host.lower()}:{parsed.port}")
    return netlocs


def _is_public_https(url: str, *, public_base_url: str) -> bool:
    if not url or not url.startswith("https://"):
        return False
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    host = (parsed.netloc or "").lower()
    hostname = (parsed.hostname or "").lower()
    local_hosts = _local_agent_netlocs(public_base_url)
    if host in local_hosts or hostname in local_hosts:
        return False
    if hostname in {"127.0.0.1", "localhost"}:
        return False
    return True


def _is_local_attachment_url(url: str, *, public_base_url: str) -> bool:
    if not url:
        return True
    if url.startswith("/"):
        return True
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    host = (parsed.netloc or "").lower()
    hostname = (parsed.hostname or "").lower()
    local_hosts = _local_agent_netlocs(public_base_url)
    return host in local_hosts or hostname in local_hosts or hostname in {
        "127.0.0.1",
        "localhost",
    }


def _maybe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
    return None


def _tool_result(payload: dict[str, Any]) -> Any:
    if payload.get("ok") is False:
        raise CreativeBridgeError(str(payload.get("error") or "Creative MCP tool failed"))
    return payload.get("result", payload)


def _extract_file_url(result: Any) -> str:
    data = _maybe_json(result)
    if not isinstance(data, dict):
        raise CreativeBridgeError("Creative upload response missing file_url")
    upload = data.get("upload") if isinstance(data.get("upload"), dict) else data
    file_url = upload.get("file_url") or data.get("file_url") or data.get("url")
    if isinstance(file_url, str) and file_url.startswith("https://"):
        return file_url
    raise CreativeBridgeError("Creative upload response missing HTTPS file_url")


def _extract_upload_instructions(result: Any) -> tuple[str, str, str | None]:
    data = _maybe_json(result)
    if not isinstance(data, dict):
        raise CreativeBridgeError("upload instructions response invalid")
    upload = data.get("upload") if isinstance(data.get("upload"), dict) else data
    put_url = upload.get("put_url") or upload.get("presigned_url") or upload.get("upload_url")
    file_url = upload.get("file_url")
    content_type = upload.get("content_type") or upload.get("Content-Type")
    if not isinstance(put_url, str) or not put_url.startswith("http"):
        raise CreativeBridgeError("upload instructions missing put_url")
    if not isinstance(file_url, str) or not file_url.startswith("https://"):
        raise CreativeBridgeError("upload instructions missing file_url")
    return put_url, file_url, content_type if isinstance(content_type, str) else None


async def _http_put(url: str, *, content: bytes, content_type: str | None) -> None:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.put(url, content=content, headers=headers or None)
        response.raise_for_status()


def _bridgeable_kinds() -> set[str]:
    return {"image", "video", "url"}


async def _resolve_one_attachment(
    *,
    session_id: str,
    attachment: dict[str, Any],
    gateway: Any,
    store: AttachmentStore,
    public_base_url: str,
) -> str:
    kind = str(attachment.get("kind") or "")
    if kind not in _bridgeable_kinds():
        raise CreativeBridgeError(f"Unsupported attachment kind: {kind}")

    url = str(attachment.get("url") or "")
    if _is_public_https(url, public_base_url=public_base_url):
        return url

    attachment_id = str(attachment.get("id") or "")
    label = str(attachment.get("label") or attachment_id or "reference")
    mime = str(attachment.get("mime") or "")
    if kind == "url" and url and not _is_local_attachment_url(url, public_base_url=public_base_url):
        if url.startswith("https://"):
            return url
        raise CreativeBridgeError(f"URL attachment is not HTTPS and cannot be bridged: {url}")
    if kind == "url" and not attachment_id:
        raise CreativeBridgeError("URL attachment missing id")

    if kind in {"image", "video"}:
        if not attachment_id:
            raise CreativeBridgeError(f"{kind} attachment missing id")
        path = store.file_path(session_id, attachment_id)
        if not path.exists():
            raise CreativeBridgeError(f"Attachment file not found: {attachment_id}")
        data = path.read_bytes()
        if not mime:
            mime = "image/jpeg" if kind == "image" else "video/mp4"
    else:
        raise CreativeBridgeError("Cannot read bytes for URL-only attachment without upload")

    filename = label if "." in label else f"{attachment_id}.bin"
    instructions_args = {
        "filename": filename,
        "mime_type": mime,
        "content_type": mime,
        "size": len(data),
    }

    try:
        raw = await gateway.call_tool(
            CREATIVE_SERVER,
            UPLOAD_INSTRUCTIONS_TOOL,
            instructions_args,
        )
        put_url, file_url, content_type = _extract_upload_instructions(_tool_result(raw))
        await _http_put(put_url, content=data, content_type=content_type or mime)
        return file_url
    except Exception as instructions_exc:
        if kind != "image" or len(data) > _BASE64_FALLBACK_MAX_BYTES:
            raise CreativeBridgeError(
                f"Creative upload instructions failed: {instructions_exc}"
            ) from instructions_exc
        try:
            raw = await gateway.call_tool(
                CREATIVE_SERVER,
                UPLOAD_REFERENCE_TOOL,
                {
                    "filename": filename,
                    "mime_type": mime,
                    "content_type": mime,
                    "content_base64": base64.b64encode(data).decode("ascii"),
                },
            )
            return _extract_file_url(_tool_result(raw))
        except Exception as fallback_exc:
            raise CreativeBridgeError(
                f"Creative reference upload failed "
                f"(instructions: {instructions_exc}; fallback: {fallback_exc})"
            ) from fallback_exc


async def resolve_creative_reference_urls(
    session_id: str,
    attachments: list[dict[str, Any]],
    *,
    gateway: Any,
    store: AttachmentStore | None = None,
    public_base_url: str | None = None,
) -> list[str]:
    """Resolve session attachments to HTTPS URLs usable by Creative generate tools."""
    if not attachments:
        return []

    base_url = (public_base_url or settings.public_base_url or "").strip()
    if store is None:
        from app.sessions import PACKAGE_ROOT

        file_store = AttachmentStore(root=PACKAGE_ROOT / "data" / "sessions")
    else:
        file_store = store

    urls: list[str] = []
    for attachment in attachments:
        kind = str(attachment.get("kind") or "")
        if kind not in _bridgeable_kinds():
            continue
        url = await _resolve_one_attachment(
            session_id=session_id,
            attachment=attachment,
            gateway=gateway,
            store=file_store,
            public_base_url=base_url,
        )
        urls.append(url)
    return urls
