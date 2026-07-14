"""Classify Creative MCP tools and parse media results for mobile UX."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

SYNC_IMAGE = {
    "creative_generate_image",
}
SYNC_VIDEO = {
    "creative_generate_video",
    "creative_image_to_video",
    "creative_first_frame_to_video",
    "creative_mux_bgm_into_video",
}
SYNC_AUDIO = {
    "creative_generate_bgm",
}
ASYNC_SUBMIT = {
    "creative_submit_workflow",
    "creative_submit_script2film",
    "creative_submit_script2film_keyframes",
    "creative_submit_batch_variants",
}
NON_MEDIA = {
    "creative_get_job",
    "creative_list_jobs",
    "creative_cancel_job",
    "creative_estimate",
    "creative_list_models",
    "creative_get_upload_instructions",
    "creative_upload_reference",
    "creative_generate_script",
}


@dataclass
class MediaToolInfo:
    suffix: str
    kind: str  # image | video | audio | other
    mode: str  # sync | async | none
    ratio: str | None = None
    label: str | None = None


@dataclass
class ParsedMediaResult:
    job_id: str | None = None
    kind: str = "other"
    urls: list[str] = field(default_factory=list)
    thumbnail_url: str | None = None
    message: str | None = None
    should_poll: bool = False
    error: str | None = None
    progress: int | None = None
    status: str | None = None


def normalize_tool_suffix(tool_name: str) -> str:
    """mcp_creative_agent_creative_generate_image → creative_generate_image."""
    name = (tool_name or "").strip()
    name = name.replace("-", "_")
    for prefix in (
        "mcp_creative_agent_",
        "mcp_creativeagent_",
        "mcp_tiktok_ads_agent_",
    ):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    if name.startswith("creative_agent_"):
        name = name[len("creative_agent_") :]
    return name


def classify_media_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> MediaToolInfo | None:
    suffix = normalize_tool_suffix(tool_name)
    if not suffix.startswith("creative_"):
        return None
    if suffix in NON_MEDIA:
        return MediaToolInfo(suffix=suffix, kind="other", mode="none")

    args = arguments or {}
    ratio = None
    for key in ("aspect_ratio", "ratio", "size"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            ratio = val.strip()
            break

    if suffix in SYNC_IMAGE:
        return MediaToolInfo(suffix=suffix, kind="image", mode="sync", ratio=ratio or "1:1", label="生成图片中")
    if suffix in SYNC_VIDEO:
        return MediaToolInfo(suffix=suffix, kind="video", mode="sync", ratio=ratio or "9:16", label="生成视频中")
    if suffix in SYNC_AUDIO:
        return MediaToolInfo(suffix=suffix, kind="audio", mode="sync", ratio=None, label="生成音频中")
    if suffix in ASYNC_SUBMIT:
        kind = "image" if "batch" in suffix or "image" in suffix else "video"
        return MediaToolInfo(
            suffix=suffix,
            kind=kind,
            mode="async",
            ratio=ratio or ("1:1" if kind == "image" else "9:16"),
            label="任务已提交，生成中",
        )
    # Unknown creative_* — treat as media-ish sync if "generate" in name
    if "generate" in suffix or "submit" in suffix:
        return MediaToolInfo(suffix=suffix, kind="other", mode="sync", ratio=ratio, label="生成中")
    return MediaToolInfo(suffix=suffix, kind="other", mode="none")


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
            # try extract first JSON object
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
    return None


def _collect_urls(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        urls = node.get("urls")
        if isinstance(urls, dict):
            for key in ("download", "preview", "url"):
                u = urls.get(key)
                if isinstance(u, str) and u.startswith("http"):
                    out.append(u)
        for key in ("download", "preview", "url", "image_url", "video_url"):
            u = node.get(key)
            if isinstance(u, str) and u.startswith("http"):
                out.append(u)
        for key in ("result_urls", "urls"):
            arr = node.get(key)
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, str) and item.startswith("http"):
                        out.append(item)
        for art in node.get("artifacts") or []:
            _collect_urls(art, out)
        for nested_key in ("result", "data", "tracking"):
            if nested_key in node and nested_key != "tracking":
                _collect_urls(node.get(nested_key), out)
    elif isinstance(node, list):
        for item in node:
            _collect_urls(item, out)


def parse_media_result(
    payload: Any,
    *,
    fallback_job_id: str,
    default_kind: str = "other",
) -> ParsedMediaResult:
    """Parse MCP gateway call_tool payload into media fields."""
    parsed = ParsedMediaResult(kind=default_kind)

    root = payload
    if isinstance(payload, dict):
        if payload.get("ok") is False:
            parsed.error = str(payload.get("error") or "MCP tool failed")
            parsed.job_id = fallback_job_id
            return parsed
        inner = payload.get("result", payload)
        root = _maybe_json(inner) if not isinstance(inner, dict) else inner
        if root is None and isinstance(inner, str):
            # plain text error/success
            parsed.message = inner[:500]
            parsed.job_id = fallback_job_id
            return parsed
    else:
        root = _maybe_json(payload)

    if not isinstance(root, dict):
        parsed.job_id = fallback_job_id
        parsed.error = "empty media result"
        return parsed

    job_id = root.get("job_id") or (root.get("tracking") or {}).get("job_id")
    if isinstance(job_id, str) and job_id.strip():
        parsed.job_id = job_id.strip()
    else:
        parsed.job_id = fallback_job_id

    tracking = root.get("tracking") if isinstance(root.get("tracking"), dict) else {}
    if tracking.get("user_message"):
        parsed.message = str(tracking["user_message"])
    if tracking.get("should_continue_polling") is True:
        parsed.should_poll = True
    if tracking.get("mode") == "async":
        parsed.should_poll = True

    status = root.get("status")
    if isinstance(status, str):
        parsed.status = status.lower()
        if parsed.status in {"queued", "processing", "running", "pending"}:
            parsed.should_poll = True
        if parsed.status in {"failed", "error", "cancelled"}:
            parsed.error = str(root.get("error") or tracking.get("user_message") or "generation failed")

    prog = root.get("progress")
    if isinstance(prog, (int, float)):
        parsed.progress = max(0, min(100, int(prog)))

    urls: list[str] = []
    _collect_urls(root, urls)
    # dedupe preserve order
    seen: set[str] = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            parsed.urls.append(u)

    if parsed.urls:
        parsed.thumbnail_url = parsed.urls[0]
        if not parsed.message:
            parsed.message = tracking.get("user_message") if tracking else None
    elif parsed.status in {"completed", "done", "success"} and not parsed.error:
        parsed.error = "generation completed but no media URL"
    elif not parsed.should_poll and not parsed.error and not parsed.urls:
        # sync tool returned without urls
        if root.get("ok") is False or root.get("error"):
            parsed.error = str(root.get("error") or "MCP tool failed")

    return parsed
