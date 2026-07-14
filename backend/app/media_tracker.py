"""Poll Creative async jobs and push media.* events via MediaHub."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.media_hub import media_hub
from app.media_parse import ParsedMediaResult, parse_media_result

DEFAULT_INTERVAL_S = 4.0
DEFAULT_TIMEOUT_S = 15 * 60.0


class MediaJobTracker:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def track(
        self,
        *,
        session_id: str,
        job_id: str,
        kind: str,
        gateway: Any,
        server: str = "creative-agent",
        interval_s: float = DEFAULT_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        key = f"{session_id}:{job_id}"
        existing = self._tasks.get(key)
        if existing and not existing.done():
            return

        async def _run() -> None:
            started = time.monotonic()
            last_progress = 5
            try:
                while True:
                    if time.monotonic() - started > timeout_s:
                        await media_hub.emit(
                            session_id,
                            {
                                "type": "media.failed",
                                "session_id": session_id,
                                "job_id": job_id,
                                "error": f"生成超时（>{int(timeout_s)}s）",
                            },
                        )
                        return
                    try:
                        raw = await gateway.call_tool(
                            server, "creative_get_job", {"job_id": job_id}
                        )
                    except Exception as exc:
                        await media_hub.emit(
                            session_id,
                            {
                                "type": "media.failed",
                                "session_id": session_id,
                                "job_id": job_id,
                                "error": str(exc),
                            },
                        )
                        return

                    parsed: ParsedMediaResult = parse_media_result(
                        raw, fallback_job_id=job_id, default_kind=kind
                    )
                    status = (parsed.status or "").lower()
                    if parsed.urls and status in {"", "completed", "done", "success"}:
                        await media_hub.emit(
                            session_id,
                            {
                                "type": "media.ready",
                                "session_id": session_id,
                                "job_id": job_id,
                                "kind": kind,
                                "urls": parsed.urls,
                                "thumbnail_url": parsed.thumbnail_url,
                                "message": parsed.message,
                            },
                        )
                        return
                    if parsed.error or status in {"failed", "error", "cancelled"}:
                        await media_hub.emit(
                            session_id,
                            {
                                "type": "media.failed",
                                "session_id": session_id,
                                "job_id": job_id,
                                "error": parsed.error or status or "failed",
                            },
                        )
                        return

                    progress = parsed.progress
                    if progress is None:
                        last_progress = min(95, last_progress + 3)
                        progress = last_progress
                    else:
                        last_progress = progress
                    await media_hub.emit(
                        session_id,
                        {
                            "type": "media.progress",
                            "session_id": session_id,
                            "job_id": job_id,
                            "progress": progress,
                            "status": status or "processing",
                            "message": parsed.message or "生成中…",
                        },
                    )
                    await asyncio.sleep(interval_s)
            finally:
                self._tasks.pop(key, None)

        self._tasks[key] = asyncio.create_task(_run())


media_tracker = MediaJobTracker()
