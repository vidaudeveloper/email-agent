"""Per-session WebSocket emitters for media progress after agent turns."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


class MediaHub:
    def __init__(self) -> None:
        self._emitters: dict[str, EmitFn] = {}
        self._lock = asyncio.Lock()

    async def bind(self, session_id: str, emit: EmitFn) -> None:
        async with self._lock:
            self._emitters[session_id] = emit

    async def unbind(self, session_id: str) -> None:
        async with self._lock:
            self._emitters.pop(session_id, None)

    async def emit(self, session_id: str, event: dict[str, Any]) -> None:
        emit = self._emitters.get(session_id)
        if emit is None:
            return
        try:
            await emit(event)
        except Exception:
            # Drop if socket already gone
            return


media_hub = MediaHub()
