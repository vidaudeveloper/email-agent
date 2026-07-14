# Mobile Cloud Session History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Cloud Agent session list / message history / delete over HTTP, and let the Flutter Experts flow reopen past chats with full replay and continued messaging.

**Architecture:** Extend existing SQLite `sessions`/`messages` with `updated_at`; add REST list/messages/delete; Flutter loads messages before WS connect; Experts page links to a history list with swipe/long-press delete.

**Tech Stack:** FastAPI, SQLite (`sessions.py`), Flutter (`go_router`, Provider), existing Cloud auth token

**Spec:** `docs/superpowers/specs/2026-07-14-mobile-cloud-session-history-design.md`  
**Worktree:** `.worktrees/cloud-agent-p0` (implement code here; docs may live on repo root)

---

## File map

| File | Responsibility |
|------|----------------|
| `cloud_agent/app/sessions.py` | `updated_at` migration; `list_sessions`; enhance `get_session_messages` (include id); `delete_session`; touch `updated_at` in `add_message` / `create_session` |
| `cloud_agent/app/main.py` | `GET /v1/sessions`, `GET /v1/sessions/{id}/messages`, `DELETE /v1/sessions/{id}` |
| `cloud_agent/tests/test_session_history.py` | API + store tests |
| `lib/cloud/models/cloud_models.dart` | `CloudSessionSummary`, `CloudHistoryMessage` |
| `lib/cloud/cloud_api_client.dart` / `cloud_client.dart` | listSessions / getSessionMessages / deleteSession |
| `lib/state/cloud_chat_controller.dart` | `start()` loads history before WS |
| `lib/features/sessions/session_history_page.dart` | History list UI + delete |
| `lib/features/experts/experts_page.dart` | Entry to history |
| `lib/app.dart` | Route `/session-history` |

---

### Task 1: Schema + session store APIs

**Files:**
- Modify: `cloud_agent/app/sessions.py`
- Create: `cloud_agent/tests/test_session_history.py`

- [ ] **Step 1: Write failing unit tests**

```python
# cloud_agent/tests/test_session_history.py
from pathlib import Path

from app import sessions as sessions_mod


def test_create_sets_updated_at(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    created = sessions_mod.create_session("vidau-creative-agent-oneclick")
    row = sessions_mod.get_session(created.session_id)
    assert row is not None
    assert row.get("updated_at")
    assert row["updated_at"] == row["created_at"]


def test_add_message_bumps_updated_at(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    created = sessions_mod.create_session("vidau-creative-agent-oneclick")
    sid = created.session_id
    before = sessions_mod.get_session(sid)["updated_at"]
    sessions_mod.add_message(sid, "user", "hello")
    after = sessions_mod.get_session(sid)["updated_at"]
    assert after >= before
    msgs = sessions_mod.get_session_messages(sid)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "id" in msgs[0]


def test_list_sessions_order_and_preview(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    a = sessions_mod.create_session("vidau-creative-agent-oneclick")
    b = sessions_mod.create_session("tiktok-ads-agent")
    sessions_mod.add_message(a.session_id, "user", "first")
    sessions_mod.add_message(b.session_id, "assistant", "second reply")
    listed = sessions_mod.list_sessions(user_id="default", limit=50, offset=0)
    assert len(listed) >= 2
    assert listed[0]["session_id"] == b.session_id
    assert "second" in listed[0]["preview"]
    assert listed[0]["message_count"] >= 1


def test_delete_session_removes_messages(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "t.db"))
    sessions_mod.init_db()
    created = sessions_mod.create_session("vidau-creative-agent-oneclick")
    sid = created.session_id
    sessions_mod.add_message(sid, "user", "bye")
    assert sessions_mod.delete_session(sid) is True
    assert sessions_mod.get_session(sid) is None
    assert sessions_mod.get_session_messages(sid) == []
    assert sessions_mod.delete_session(sid) is False
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/test_session_history.py -v
```

- [ ] **Step 3: Implement in `sessions.py`**

- `init_db`: after CREATE, if `updated_at` column missing → `ALTER TABLE sessions ADD COLUMN updated_at TEXT` and `UPDATE sessions SET updated_at = created_at WHERE updated_at IS NULL`
- Prefer CREATE TABLE with `updated_at` for fresh DBs
- `create_session`: insert `updated_at` same as `created_at`
- `get_session`: select `updated_at`
- `add_message`: after insert, `UPDATE sessions SET updated_at = ? WHERE id = ?`
- `get_session_messages`: `SELECT id, role, content, created_at ...`
- `list_sessions(user_id, *, expert_id=None, limit=50, offset=0) -> list[dict]`:
  - Join/lookup expert name via `get_expert`
  - Preview: last message with role in (`user`,`assistant`), truncate to 80 chars
  - `message_count` subquery or COUNT
  - Order by `COALESCE(updated_at, created_at) DESC`
- `delete_session(session_id) -> bool`: delete messages, delete session row; optionally `shutil.rmtree(PACKAGE_ROOT / "data" / "sessions" / session_id, ignore_errors=True)`; return False if missing

- [ ] **Step 4: pytest pass**

- [ ] **Step 5: Commit**

```bash
git add cloud_agent/app/sessions.py cloud_agent/tests/test_session_history.py
git commit -m "feat(cloud-agent): session list/delete and updated_at"
```

---

### Task 2: HTTP routes

**Files:**
- Modify: `cloud_agent/app/main.py`
- Modify: `cloud_agent/tests/test_session_history.py` (add TestClient tests)

- [ ] **Step 1: Add API tests**

```python
from fastapi.testclient import TestClient
from app.main import app

AUTH = {"Authorization": "Bearer dev-local-token"}


def test_http_list_messages_delete(tmp_path, monkeypatch):
    from app import sessions as sessions_mod
    monkeypatch.setattr(sessions_mod.settings, "sqlite_path", str(tmp_path / "api.db"))
    sessions_mod.init_db()
    client = TestClient(app)
    sid = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "vidau-creative-agent-oneclick"},
    ).json()["session_id"]
    sessions_mod.add_message(sid, "user", "hi there")
    listed = client.get("/v1/sessions", headers=AUTH)
    assert listed.status_code == 200
    assert any(s["session_id"] == sid for s in listed.json()["sessions"])
    msgs = client.get(f"/v1/sessions/{sid}/messages", headers=AUTH)
    assert msgs.status_code == 200
    assert msgs.json()["messages"][0]["content"] == "hi there"
    deleted = client.delete(f"/v1/sessions/{sid}", headers=AUTH)
    assert deleted.status_code == 200
    assert client.get(f"/v1/sessions/{sid}/messages", headers=AUTH).status_code == 404
```

Also test: unauthorized → 401; unknown session messages → 404.

- [ ] **Step 2: Implement routes in `main.py`**

```python
@app.get("/v1/sessions")
def sessions_list(
    expert_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: str = Depends(verify_token),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    items = list_sessions(user_id="default", expert_id=expert_id, limit=limit, offset=offset)
    return {"sessions": items}

@app.get("/v1/sessions/{session_id}/messages")
def sessions_messages(session_id: str, _: str = Depends(verify_token)):
    if get_session(session_id) is None:
        raise HTTPException(404, "Session not found")
    return {"session_id": session_id, "messages": get_session_messages(session_id)}

@app.delete("/v1/sessions/{session_id}")
def sessions_delete(session_id: str, _: str = Depends(verify_token)):
    if not delete_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"ok": True}
```

Note: Attachment routes under `/v1/sessions/{id}/attachments` remain unchanged.

- [ ] **Step 3: pytest pass**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(cloud-agent): session history HTTP API"
```

---

### Task 3: Flutter models + API client

**Files:**
- Modify: `lib/cloud/models/cloud_models.dart`
- Modify: `lib/cloud/cloud_api_client.dart`
- Modify: `lib/cloud/cloud_client.dart`

- [ ] **Step 1: Add models**

```dart
class CloudSessionSummary {
  const CloudSessionSummary({
    required this.sessionId,
    required this.expertId,
    required this.expertName,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
    required this.messageCount,
    this.preview = '',
  });
  final String sessionId;
  final String expertId;
  final String expertName;
  final String status;
  final String createdAt;
  final String updatedAt;
  final int messageCount;
  final String preview;
  factory CloudSessionSummary.fromJson(Map<String, dynamic> j) => CloudSessionSummary(
    sessionId: j['session_id'] as String,
    expertId: j['expert_id'] as String? ?? '',
    expertName: j['expert_name'] as String? ?? '',
    status: j['status'] as String? ?? '',
    createdAt: j['created_at'] as String? ?? '',
    updatedAt: j['updated_at'] as String? ?? j['created_at'] as String? ?? '',
    messageCount: (j['message_count'] as num?)?.toInt() ?? 0,
    preview: j['preview'] as String? ?? '',
  );
}

class CloudHistoryMessage {
  const CloudHistoryMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
  });
  final int id;
  final String role;
  final String content;
  final String createdAt;
  factory CloudHistoryMessage.fromJson(Map<String, dynamic> j) => CloudHistoryMessage(
    id: (j['id'] as num).toInt(),
    role: j['role'] as String,
    content: j['content'] as String? ?? '',
    createdAt: j['created_at'] as String? ?? '',
  );
}
```

- [ ] **Step 2: API methods** (follow existing `createSession` / header patterns)

```dart
Future<List<CloudSessionSummary>> listSessions({String? expertId, int limit = 50, int offset = 0});
Future<List<CloudHistoryMessage>> getSessionMessages(String sessionId);
Future<void> deleteSession(String sessionId);
```

Paths: `GET /v1/sessions`, `GET /v1/sessions/$id/messages`, `DELETE /v1/sessions/$id`.

- [ ] **Step 3: Facade on `CloudClient`**

- [ ] **Step 4: `dart analyze` on touched files**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(mobile): cloud session history API client"
```

---

### Task 4: Chat controller loads history on start

**Files:**
- Modify: `lib/state/cloud_chat_controller.dart`

- [ ] **Step 1: Change `start()`**

Order:
1. Clear local state
2. Subscribe to events
3. `GET getSessionMessages(sessionId)` — map `user`/`assistant` to `CloudDisplayMessage` (id `hist-$id`)
4. On failure: set `error`, do not connect WS
5. Else `connectSession` + `listAttachments` as today

```dart
try {
  final history = await _cloud.getSessionMessages(sessionId);
  for (final m in history) {
    if (m.role != 'user' && m.role != 'assistant') continue;
    messages.add(CloudDisplayMessage(
      id: 'hist-${m.id}',
      kind: m.role == 'user' ? CloudMessageKind.user : CloudMessageKind.assistant,
      text: m.content,
    ));
  }
  await _cloud.connectSession(sessionId: sessionId);
  final existing = await _cloud.listAttachments(sessionId);
  _sessionAttachments.addAll(existing);
} catch (e) {
  error = e.toString();
  notifyListeners();
  return;
}
```

- [ ] **Step 2: Analyze**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(mobile): replay cloud session history on chat open"
```

---

### Task 5: Session history page + Experts entry + route

**Files:**
- Create: `lib/features/sessions/session_history_page.dart`
- Modify: `lib/features/experts/experts_page.dart`
- Modify: `lib/app.dart`

- [ ] **Step 1: Route** `/session-history` → `SessionHistoryPage`

- [ ] **Step 2: `SessionHistoryPage`**

- Pull-to-refresh: `listSessions()`
- ListTile: expertName / preview / time
- Tap → `push('/cloud-chat/$sessionId', extra: {name, expertId})`
- Long-press or Dismissible → confirm → `deleteSession` → refresh
- Empty: 「还没有会话，从上方专家开始聊天」

- [ ] **Step 3: Experts AppBar history IconButton** → `/session-history`

- [ ] **Step 4: Pass `expertId` into chat route when available**

- [ ] **Step 5: analyze + commit**

```bash
git commit -m "feat(mobile): session history list on Experts"
```

---

### Task 6: Verification

- [ ] **Step 1: Backend pytest** `tests/test_session_history.py` + full suite (pre-existing fails OK)

- [ ] **Step 2: Flutter analyze** on touched lib paths

- [ ] **Step 3: Manual** — new chat appears in history; reopen restores bubbles; delete works; empty state

---

## Spec coverage self-check

| Spec item | Task |
|-----------|------|
| `updated_at` + list/preview | 1 |
| GET list / messages / DELETE | 2 |
| Flutter clients | 3 |
| start() replay + WS | 4 |
| Experts entry + history UI + delete | 5 |
| Acceptance | 6 |
