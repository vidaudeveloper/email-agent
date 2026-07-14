"""OpenAI-compatible tool-calling agent loop for Expert sessions."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.attachments import AttachmentStore
from app.catalog import get_expert_raw, load_catalog_skills
from app.config import settings
from app.creative_bridge import (
    CreativeBridgeError,
    apply_creative_reference_urls,
    expert_needs_creative_bridge,
    needs_creative_reference_bridge,
    resolve_creative_reference_urls,
)
from app.expert_install import get_installed_skills, load_skill_bodies
from app.llm_config import effective_llm_mode, resolve_llm_config
from app.mcp_gateway import MOCK_TOOLS, McpGateway, McpGatewayError, _external_tool_name, _strip_prefix
from app.media_hub import media_hub
from app.media_parse import classify_media_tool, parse_media_result
from app.media_tracker import media_tracker
from app.sandbox import get_sandbox_provider
from app.sessions import PACKAGE_ROOT, add_message, get_session, get_session_messages
SANDBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sandbox_write_file",
            "description": "Write a text file inside the session local sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_read_file",
            "description": "Read a text file from the session local sandbox.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_run_command",
            "description": (
                "Run a short shell command in the session local sandbox workspace. "
                "Do NOT use curl/wget/http to fetch session attachment URLs — "
                "attachments are already available to creative_* tools via reference injection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_sec": {
                        "type": "number",
                        "description": "Max seconds (capped at 30).",
                    },
                },
                "required": ["command"],
            },
        },
    },
]


def _event(event_type: str, session_id: str, **fields) -> dict:
    return {"type": event_type, "session_id": session_id, **fields}


def build_attachment_context(attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return ""
    lines = [
        "[Attachments]",
        "These files are already stored on the Cloud Agent. "
        "Do NOT curl/wget/download them via sandbox_run_command. "
        "For creative_* tools, reference_urls are injected automatically.",
    ]
    for att in attachments:
        ref = att.get("ref") or ""
        kind = att.get("kind") or ""
        mime = att.get("mime") or kind or ""
        att_id = att.get("id") or ""
        # Prefer id/ref over local preview URLs so the model does not try to fetch them.
        lines.append(f"- {ref} id={att_id} kind={kind} mime={mime}")
    return "\n".join(lines)


def enrich_user_content(content: str, attachments: list[dict[str, Any]]) -> str:
    block = build_attachment_context(attachments)
    if not block:
        return content
    if content.strip():
        return f"{content.strip()}\n\n{block}"
    return block


def build_system_prompt(expert: dict) -> str:
    expert_id = expert["id"]
    skill_ids = get_installed_skills(expert_id) or list(expert.get("skills") or [])
    # include remote source ids as skill fallbacks
    for src in expert.get("remote_skill_sources") or []:
        sid = str(src.get("id") or "")
        if sid and sid not in skill_ids:
            skill_ids.append(sid)
    bodies = load_skill_bodies(skill_ids, load_catalog_skills())
    parts = [
        f'[IMPORTANT: This session uses the "{expert.get("name")}" expert profile.]',
        str(expert.get("activation_prompt") or "").strip(),
    ]
    for body in bodies:
        parts.append(
            "[IMPORTANT: The following skill is preloaded for this session.]\n" + body
        )
    parts.append(
        "Use MCP tools (mcp_*) for external business APIs. "
        "Use sandbox_* tools for local files/commands when needed. "
        "Ask for missing parameters instead of inventing credentials. "
        "Never use sandbox_run_command to download or delete session attachment URLs; "
        "call creative_* tools and let the server inject reference_urls."
    )
    parts.append(
        "Creative generation UX (align with desktop):\n"
        "- Before creative_generate_image / video, ask 1–2 clarifying questions "
        "(style + aspect ratio) unless the user already provided them.\n"
        "- Tell the user generation may take 1–2 minutes before calling the tool.\n"
        "- After tools return, summarize in text only (credits, brief caption). "
        "Do NOT embed images with Markdown ![alt](url) or <img> — the mobile app "
        "already shows a dedicated media card from media.ready."
    )
    return "\n\n".join(p for p in parts if p)


async def _call_mcp_with_heartbeats(
    *,
    session_id: str,
    gateway: McpGateway,
    server: str,
    tool: str,
    args: dict[str, Any],
    job_id: str,
    media_kind: str,
    label: str,
) -> AsyncIterator[dict]:
    """Run a long MCP call while yielding media.progress heartbeats."""
    task = asyncio.create_task(gateway.call_tool(server, tool, args))
    progress = 8
    try:
        while not task.done():
            yield _event(
                "media.progress",
                session_id,
                job_id=job_id,
                progress=progress,
                status="processing",
                message=f"{label}…约需 1–2 分钟",
            )
            yield _event(
                "chat.progress",
                session_id,
                content=f"{label}…{progress}%（云端生成中，请稍候）",
            )
            progress = min(92, progress + 6)
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
            except asyncio.TimeoutError:
                continue
        yield {"__mcp_result__": task.result()}
    except Exception as exc:
        if not task.done():
            task.cancel()
        yield {"__mcp_result__": {"ok": False, "error": str(exc)}}


async def _mcp_tool_schemas(expert: dict, gateway: McpGateway) -> list[dict]:
    tools: list[dict] = []
    for server in expert.get("requires_mcp") or []:
        try:
            listed = await gateway.list_tools(server)
        except Exception:
            # Real MCP may 401/timeout — fall back to catalog stubs so LLM can still reply
            stubs = [item["tool"] for item in MOCK_TOOLS.get(server, [])] or ["help"]
            listed = [
                {
                    "name": _external_tool_name(server, stubs[0]),
                    "description": f"Fallback stub for {server} (MCP unavailable)",
                }
            ]
        for item in listed:
            # OpenAI function names: [a-zA-Z0-9_-]
            safe_name = item["name"].replace("-", "_")
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": safe_name,
                        "description": f"{item.get('description') or item['name']} (server={server})",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "arguments": {
                                    "type": "object",
                                    "description": "Tool arguments as a JSON object",
                                    "additionalProperties": True,
                                }
                            },
                            "additionalProperties": True,
                        },
                    },
                }
            )
    return tools


def _parse_tool_name(name: str) -> tuple[str, str] | None:
    raw = name
    mapping = [
        ("mcp_tiktok_ads_agent_", "tiktok-ads-agent"),
        ("mcp_creative_agent_", "creative-agent"),
        ("mcp_vidau_geo_", "vidau-geo"),
        ("mcp_tiktok-ads-agent_", "tiktok-ads-agent"),
        ("mcp_creative-agent_", "creative-agent"),
        ("mcp_vidau-geo_", "vidau-geo"),
    ]
    for prefix, server in mapping:
        if raw.startswith(prefix):
            return server, raw[len(prefix) :]
    if raw.startswith("mcp_"):
        rest = raw[4:]
        for server in ("tiktok-ads-agent", "creative-agent", "vidau-geo"):
            token = server.replace("-", "_") + "_"
            if rest.startswith(token):
                return server, rest[len(token) :]
    return None


def _sandbox_tools_for_expert(expert: dict) -> list[dict]:
    toolsets = set(expert.get("toolsets") or [])
    if toolsets & {"file", "terminal", "vision"}:
        return list(SANDBOX_TOOLS)
    if (expert.get("sandbox_policy") or "never") != "never":
        return list(SANDBOX_TOOLS)
    return []


async def _chat_completion(llm, messages: list[dict], tools: list[dict], tool_choice: str | None = "auto") -> dict:
    url = f"{llm.base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": llm.model,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
    headers = {
        "Authorization": f"Bearer {llm.api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code >= 400:
            raise RuntimeError(f"LLM error {res.status_code}: {res.text[:500]}")
        return res.json()


def _assistant_text(message: dict) -> str:
    """Some models (e.g. deepseek-v4-flash) return empty content + reasoning_content only."""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        joined = "\n".join(p for p in parts if p).strip()
        if joined:
            return joined
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        # Prefer not to dump full chain-of-thought; use last non-empty line as hint
        lines = [ln.strip() for ln in reasoning.strip().splitlines() if ln.strip()]
        if lines:
            return lines[-1]
    return ""


async def run_agent_loop(
    session_id: str,
    user_content: str,
    *,
    attachments: list[dict[str, Any]] | None = None,
) -> AsyncIterator[dict]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    msg_id = str(uuid.uuid4())
    expert = get_expert_raw(session["expert_id"])
    sandbox = get_sandbox_provider(settings)
    gateway = McpGateway(settings, user_id=session["user_id"])
    mcp_mode = settings.effective_mcp_mode()

    yield _event("sandbox.status", session_id, status=sandbox.provider)
    yield _event(
        "session.meta",
        session_id,
        mcp_mode=mcp_mode,
        llm_mode=effective_llm_mode(),
        expert_id=expert["id"],
    )
    public_attachments = attachments or []
    stored_content = enrich_user_content(user_content, public_attachments)
    resolved_creative_urls: list[str] | None = None
    attachment_store: AttachmentStore | None = None
    chat_user_fields: dict[str, Any] = {
        "content": user_content,
        "msg_id": msg_id,
    }
    if public_attachments:
        chat_user_fields["attachments"] = public_attachments
    yield _event("chat.user", session_id, **chat_user_fields)
    add_message(session_id, "user", stored_content)

    mode = effective_llm_mode()
    if mode != "openai_compatible":
        yield _event(
            "chat.assistant",
            session_id,
            content=(
                "未配置可用 LLM，无法运行真实 Expert tool-calling 循环。\n"
                "请使用 Vidau 账号登录，或设置 OPENVIDAU_API_KEY / CLOUD_AGENT_LLM_*。"
            ),
        )
        add_message(session_id, "assistant", "LLM not configured")
        yield _event("chat.done", session_id)
        return

    llm = resolve_llm_config()
    yield _event(
        "chat.progress",
        session_id,
        content=f"准备工具与模型（{llm.model}）…",
    )
    system_prompt = build_system_prompt(expert)
    tools = await _mcp_tool_schemas(expert, gateway)
    tools.extend(_sandbox_tools_for_expert(expert))

    history = get_session_messages(session_id)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for row in history:
        if row["role"] in {"user", "assistant"} and row["content"]:
            messages.append({"role": row["role"], "content": row["content"]})

    yield _event("chat.progress", session_id, content=f"Expert 循环中（mcp={mcp_mode}, model={llm.model}）…")

    final_text = ""
    for turn in range(max(1, settings.llm_max_turns)):
        yield _event("chat.progress", session_id, content=f"LLM turn {turn + 1}/{settings.llm_max_turns}")
        try:
            data = await _chat_completion(llm, messages, tools)
        except Exception as exc:
            yield _event("chat.assistant", session_id, content=f"LLM 调用失败：{exc}")
            add_message(session_id, "assistant", str(exc))
            yield _event("chat.done", session_id)
            return

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        content = _assistant_text(message)

        if not tool_calls:
            if not content:
                # deepseek-style empty content: force a plain-language reply
                yield _event("chat.progress", session_id, content="模型未返回正文，正在重试…")
                try:
                    retry_messages = list(messages) + [
                        {
                            "role": "user",
                            "content": "请直接用一两句中文回答用户的上一条问题，不要只做内部思考。",
                        }
                    ]
                    data2 = await _chat_completion(llm, retry_messages, tools=[], tool_choice=None)
                    message2 = ((data2.get("choices") or [{}])[0].get("message")) or {}
                    content = _assistant_text(message2)
                except Exception as exc:
                    content = f"LLM 重试失败：{exc}"
            final_text = content or "模型没有返回可用内容，请换个问法再试。"
            break

        messages.append(
            {
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            }
        )

        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = str(fn.get("name") or "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if isinstance(args, dict) and isinstance(args.get("arguments"), dict):
                nested = args.pop("arguments")
                args = {**nested, **args}

            yield _event("tool.mcp", session_id, tool=name, phase="start")
            result_payload: Any
            tool_call_id = str(tc.get("id") or uuid.uuid4())
            media_info = classify_media_tool(name, args if isinstance(args, dict) else {})
            media_job_id = f"local-{tool_call_id}"

            if media_info and media_info.mode in {"sync", "async"}:
                yield _event(
                    "media.placeholder",
                    session_id,
                    job_id=media_job_id,
                    kind=media_info.kind,
                    tool=name,
                    ratio=media_info.ratio,
                    label=media_info.label or "生成中",
                )

            if name in {
                "sandbox_write_file",
                "sandbox_read_file",
                "sandbox_run_command",
            }:
                state = await sandbox.allocate(session_id)
                yield _event(
                    "sandbox.status",
                    session_id,
                    status="ready" if state.allocated else sandbox.provider,
                    workspace=state.workspace,
                )
                try:
                    if name == "sandbox_write_file":
                        path = await sandbox.write_file(
                            session_id, str(args.get("path")), str(args.get("content"))
                        )
                        result_payload = {"ok": True, "path": path}
                    elif name == "sandbox_read_file":
                        text = await sandbox.read_file(session_id, str(args.get("path")))
                        result_payload = {"ok": True, "content": text}
                    else:
                        timeout = min(float(args.get("timeout_sec") or 30), 30.0)
                        cmd = await sandbox.run_command(
                            session_id,
                            str(args.get("command")),
                            timeout,
                        )
                        result_payload = {
                            "ok": cmd.ok,
                            "stdout": cmd.stdout,
                            "stderr": cmd.stderr,
                            "exit_code": cmd.exit_code,
                        }
                except Exception as exc:
                    result_payload = {"ok": False, "error": str(exc)}
            else:
                parsed = _parse_tool_name(name)
                if not parsed:
                    result_payload = {"ok": False, "error": f"Unknown tool {name}"}
                else:
                    server, tool = parsed
                    tool = _strip_prefix(server, tool)
                    try:
                        if (
                            expert_needs_creative_bridge(expert)
                            and needs_creative_reference_bridge(name)
                            and public_attachments
                        ):
                            if resolved_creative_urls is None:
                                if attachment_store is None:
                                    attachment_store = AttachmentStore(
                                        root=PACKAGE_ROOT / "data" / "sessions"
                                    )
                                resolved_creative_urls = (
                                    await resolve_creative_reference_urls(
                                        session_id,
                                        public_attachments,
                                        gateway=gateway,
                                        store=attachment_store,
                                    )
                                )
                            if isinstance(args, dict):
                                args = apply_creative_reference_urls(
                                    name, args, resolved_creative_urls
                                )
                        if media_info and media_info.mode == "sync":
                            result_payload = {"ok": False, "error": "empty"}
                            async for hb in _call_mcp_with_heartbeats(
                                session_id=session_id,
                                gateway=gateway,
                                server=server,
                                tool=tool,
                                args=args,
                                job_id=media_job_id,
                                media_kind=media_info.kind,
                                label=media_info.label or "生成中",
                            ):
                                if isinstance(hb, dict) and "__mcp_result__" in hb:
                                    result_payload = hb["__mcp_result__"]
                                else:
                                    yield hb
                        else:
                            result_payload = await gateway.call_tool(server, tool, args)
                    except CreativeBridgeError as exc:
                        result_payload = {"ok": False, "error": str(exc)}
                    except McpGatewayError as exc:
                        result_payload = {"ok": False, "error": str(exc)}

            if media_info and media_info.mode in {"sync", "async"}:
                parsed_media = parse_media_result(
                    result_payload,
                    fallback_job_id=media_job_id,
                    default_kind=media_info.kind,
                )
                if parsed_media.job_id and not str(parsed_media.job_id).startswith("local-"):
                    # Remap placeholder id → real job id for the client
                    if parsed_media.job_id != media_job_id:
                        yield _event(
                            "media.placeholder",
                            session_id,
                            job_id=parsed_media.job_id,
                            kind=media_info.kind,
                            tool=name,
                            ratio=media_info.ratio,
                            label=media_info.label or "生成中",
                        )
                        media_job_id = parsed_media.job_id

                if parsed_media.error and not parsed_media.urls:
                    yield _event(
                        "media.failed",
                        session_id,
                        job_id=media_job_id,
                        error=parsed_media.error,
                    )
                elif parsed_media.urls and not parsed_media.should_poll:
                    yield _event(
                        "media.ready",
                        session_id,
                        job_id=media_job_id,
                        kind=media_info.kind,
                        urls=parsed_media.urls,
                        thumbnail_url=parsed_media.thumbnail_url,
                        message=parsed_media.message,
                    )
                elif parsed_media.should_poll and parsed_media.job_id:
                    media_tracker.track(
                        session_id=session_id,
                        job_id=parsed_media.job_id,
                        kind=media_info.kind,
                        gateway=gateway,
                    )
                    await media_hub.emit(
                        session_id,
                        _event(
                            "media.progress",
                            session_id,
                            job_id=parsed_media.job_id,
                            progress=parsed_media.progress or 10,
                            status=parsed_media.status or "queued",
                            message=parsed_media.message or "任务排队中…",
                        ),
                    )

            yield _event("tool.mcp", session_id, tool=name, phase="end")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(result_payload, ensure_ascii=False)[:8000],
                }
            )
    else:
        final_text = final_text or "达到最大工具循环次数，请补充信息后重试。"

    yield _event("chat.assistant", session_id, content=final_text)
    add_message(session_id, "assistant", final_text)
    yield _event("chat.done", session_id)
