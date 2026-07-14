from __future__ import annotations

from collections.abc import AsyncIterator

from app.agent_loop import run_agent_loop


async def stream_user_message(
    session_id: str,
    content: str,
    *,
    attachments: list | None = None,
) -> AsyncIterator[dict]:
    """Delegate to the real Expert agent loop (LLM + MCP + sandbox)."""
    async for event in run_agent_loop(
        session_id,
        content,
        attachments=attachments or [],
    ):
        yield event
