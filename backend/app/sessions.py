from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.catalog import get_expert
from app.config import settings
from app.llm_config import effective_llm_mode
from app.models import SandboxInfo, SessionCreateResponse

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _sqlite_file() -> Path:
    path = Path(settings.sqlite_path)
    if path.is_absolute():
        return path
    return PACKAGE_ROOT / path


def _connect() -> sqlite3.Connection:
    db_path = _sqlite_file()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_sessions_updated_at(conn: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT")
        conn.execute(
            "UPDATE sessions SET updated_at = created_at WHERE updated_at IS NULL"
        )


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                expert_id TEXT,
                user_id TEXT NOT NULL DEFAULT 'default',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS session_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn_id TEXT NOT NULL DEFAULT '',
                tool TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT
            );

            CREATE TABLE IF NOT EXISTS session_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'other',
                state TEXT NOT NULL,
                urls_json TEXT NOT NULL DEFAULT '[]',
                thumbnail_url TEXT,
                ratio TEXT,
                error TEXT,
                label TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(session_id, job_id)
            );
            """
        )
        _migrate_sessions_updated_at(conn)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_status(expert_id: str, user_id: str) -> tuple[str, list[str]]:
    """Allow chat when Skills are installed; missing MCP apiKey is soft (desktop-aligned)."""
    detail = get_expert(expert_id, user_id)
    if detail.status == "coming_soon":
        return "needs_setup", []
    if detail.status == "needs_setup":
        return "needs_setup", []
    # Soft: report missing keys but still ready for Skill Q&A
    missing = list(detail.mcp_credentials_missing or [])
    return "ready", missing


def create_session(
    expert_id: str,
    user_id: str = "default",
) -> SessionCreateResponse:
    init_db()
    expert = get_expert(expert_id, user_id)
    status, missing = _session_status(expert.id, user_id)
    session_id = str(uuid.uuid4())
    created_at = _now_iso()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, expert_id, user_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, expert.id, user_id, status, created_at, created_at),
        )

    return SessionCreateResponse(
        session_id=session_id,
        status=status,  # type: ignore[arg-type]
        sandbox=SandboxInfo(
            provider=settings.sandbox_provider,
            allocated=False,
        ),
        missing_credentials=missing,
        mcp_mode=settings.effective_mcp_mode(),
        llm_mode=effective_llm_mode(),
        expert_name=expert.name,
    )


def get_session(session_id: str) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, expert_id, user_id, status, created_at, updated_at
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_session_messages(session_id: str) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, created_at FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_message(session_id: str, role: str, content: str) -> None:
    init_db()
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )


def _preview_text(content: str, max_len: int = 80) -> str:
    if len(content) <= max_len:
        return content
    return content[: max_len - 1] + "…"


def list_sessions(
    user_id: str,
    *,
    expert_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    init_db()
    query = """
        SELECT
            s.id AS session_id,
            s.expert_id,
            s.user_id,
            s.status,
            s.created_at,
            s.updated_at,
            (
                SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id
            ) AS message_count,
            (
                SELECT m.content FROM messages m
                WHERE m.session_id = s.id AND m.role IN ('user', 'assistant')
                ORDER BY m.id DESC
                LIMIT 1
            ) AS preview_content
        FROM sessions s
        WHERE s.user_id = ?
    """
    params: list[object] = [user_id]
    if expert_id is not None:
        query += " AND s.expert_id = ?"
        params.append(expert_id)
    query += """
        ORDER BY COALESCE(s.updated_at, s.created_at) DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    results: list[dict] = []
    for row in rows:
        item = dict(row)
        preview_content = item.pop("preview_content") or ""
        item["preview"] = _preview_text(preview_content)
        expert = get_expert(item["expert_id"], user_id)
        item["expert_name"] = expert.name
        results.append(item)
    return results


def delete_session(session_id: str) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_steps WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_media WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    attachment_dir = PACKAGE_ROOT / "data" / "sessions" / session_id
    shutil.rmtree(attachment_dir, ignore_errors=True)
    return True


def _tool_label(tool: str) -> str:
    name = tool or ""
    for prefix in ("mcp_creative-agent_", "mcp_creative_agent_", "mcp_"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    mapping = {
        "creative_generate_image": "生成图片",
        "creative_generate_video": "生成视频",
        "creative_image_to_video": "图生视频",
        "creative_first_frame_to_video": "首帧生视频",
        "creative_generate_bgm": "生成音频",
        "creative_submit_workflow": "执行工作流",
        "creative_submit_script2film": "脚本成片",
        "creative_get_job": "查询任务",
    }
    return mapping.get(name, name or "执行工具")


def upsert_step_start(
    session_id: str,
    tool: str,
    *,
    turn_id: str = "",
    label: str | None = None,
) -> None:
    init_db()
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO session_steps
                (session_id, turn_id, tool, label, status, started_at, ended_at)
            VALUES (?, ?, ?, ?, 'running', ?, NULL)
            """,
            (session_id, turn_id, tool, label or _tool_label(tool), now),
        )


def upsert_step_end(
    session_id: str,
    tool: str,
    *,
    status: str = "done",
) -> None:
    init_db()
    now = _now_iso()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM session_steps
            WHERE session_id = ? AND tool = ? AND status = 'running'
            ORDER BY id DESC LIMIT 1
            """,
            (session_id, tool),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO session_steps
                    (session_id, turn_id, tool, label, status, started_at, ended_at)
                VALUES (?, '', ?, ?, ?, ?, ?)
                """,
                (session_id, tool, _tool_label(tool), status, now, now),
            )
            return
        conn.execute(
            """
            UPDATE session_steps
            SET status = ?, ended_at = ?
            WHERE id = ?
            """,
            (status, now, row["id"]),
        )


def upsert_media(
    session_id: str,
    job_id: str,
    *,
    kind: str = "other",
    state: str,
    urls: list[str] | None = None,
    thumbnail_url: str | None = None,
    ratio: str | None = None,
    error: str | None = None,
    label: str | None = None,
) -> None:
    init_db()
    now = _now_iso()
    urls_json = json.dumps(urls or [], ensure_ascii=False)
    with _connect() as conn:
        existing = conn.execute(
            """
            SELECT id, kind, urls_json, thumbnail_url, ratio, label, created_at
            FROM session_media
            WHERE session_id = ? AND job_id = ?
            """,
            (session_id, job_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO session_media (
                    session_id, job_id, kind, state, urls_json,
                    thumbnail_url, ratio, error, label, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    job_id,
                    kind,
                    state,
                    urls_json,
                    thumbnail_url,
                    ratio,
                    error,
                    label,
                    now,
                    now,
                ),
            )
            return
        conn.execute(
            """
            UPDATE session_media SET
                kind = ?,
                state = ?,
                urls_json = ?,
                thumbnail_url = ?,
                ratio = ?,
                error = ?,
                label = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                kind or existing["kind"],
                state,
                urls_json if urls is not None else existing["urls_json"],
                thumbnail_url
                if thumbnail_url is not None
                else existing["thumbnail_url"],
                ratio if ratio is not None else existing["ratio"],
                error,
                label if label is not None else existing["label"],
                now,
                existing["id"],
            ),
        )


def persist_timeline_event(event: dict[str, Any]) -> None:
    """Best-effort persistence for WS timeline events."""
    event_type = event.get("type")
    session_id = event.get("session_id")
    if not session_id or not event_type:
        return
    try:
        if event_type == "tool.mcp":
            tool = str(event.get("tool") or "")
            phase = str(event.get("phase") or "")
            if phase == "start":
                upsert_step_start(session_id, tool)
            elif phase == "end":
                upsert_step_end(session_id, tool, status="done")
            return
        if event_type == "media.placeholder":
            upsert_media(
                session_id,
                str(event.get("job_id") or ""),
                kind=str(event.get("kind") or "other"),
                state="pending",
                ratio=event.get("ratio"),
                label=event.get("label"),
            )
            return
        if event_type == "media.progress":
            job_id = str(event.get("job_id") or "")
            if not job_id:
                return
            upsert_media(
                session_id,
                job_id,
                kind=str(event.get("kind") or "other"),
                state="generating",
                label=event.get("message") or event.get("label"),
            )
            return
        if event_type == "media.ready":
            upsert_media(
                session_id,
                str(event.get("job_id") or ""),
                kind=str(event.get("kind") or "other"),
                state="ready",
                urls=list(event.get("urls") or []),
                thumbnail_url=event.get("thumbnail_url"),
                label=event.get("message") or event.get("label"),
            )
            return
        if event_type == "media.failed":
            upsert_media(
                session_id,
                str(event.get("job_id") or ""),
                kind=str(event.get("kind") or "other"),
                state="failed",
                error=str(event.get("error") or "生成失败"),
            )
    except Exception:
        # Persistence must not break the live WS stream.
        return


def get_session_timeline(session_id: str) -> list[dict[str, Any]]:
    """Interleaved timeline: messages, step groups, media."""
    init_db()
    with _connect() as conn:
        messages = [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, role, content, created_at FROM messages
                WHERE session_id = ? AND role IN ('user', 'assistant')
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        ]
        steps = [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, turn_id, tool, label, status, started_at, ended_at
                FROM session_steps
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        ]
        media_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT job_id, kind, state, urls_json, thumbnail_url, ratio,
                       error, label, created_at, updated_at
                FROM session_media
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        ]

    items: list[dict[str, Any]] = []
    for m in messages:
        items.append(
            {
                "type": "message",
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"],
                "sort_at": m["created_at"],
            }
        )

    if steps:
        # Group contiguous steps into one block for history (default collapsed).
        step_items = [
            {
                "tool": s["tool"],
                "label": s["label"] or _tool_label(s["tool"]),
                "status": s["status"],
                "started_at": s["started_at"],
                "ended_at": s["ended_at"],
            }
            for s in steps
        ]
        items.append(
            {
                "type": "steps",
                "turn_id": steps[0].get("turn_id") or "",
                "collapsed_default": True,
                "steps": step_items,
                "created_at": steps[0]["started_at"],
                "sort_at": steps[0]["started_at"],
            }
        )

    for row in media_rows:
        try:
            urls = json.loads(row["urls_json"] or "[]")
        except json.JSONDecodeError:
            urls = []
        if not isinstance(urls, list):
            urls = []
        items.append(
            {
                "type": "media",
                "job_id": row["job_id"],
                "kind": row["kind"],
                "state": row["state"],
                "urls": [u for u in urls if isinstance(u, str)],
                "thumbnail_url": row["thumbnail_url"],
                "ratio": row["ratio"],
                "error": row["error"],
                "label": row["label"],
                "created_at": row["created_at"],
                "sort_at": row["created_at"],
            }
        )

    items.sort(key=lambda x: (x.get("sort_at") or "", str(x.get("type"))))
    for item in items:
        item.pop("sort_at", None)
    return items
