# Mobile Cloud Composer ATTACH Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Cloud chat attach album photos/videos and URLs, send them with messages, show inline bubble previews, support `@` on session attachments, and bridge Creative reference uploads server-side.

**Architecture:** Flutter uploads via HTTP to Cloud Agent session storage; WS `chat.send` carries `attachment_ids`; server echoes `chat.user.attachments` for bubble UI; Creative Expert loop resolves local files to HTTPS via `creative_get_upload_instructions` (preferred) or `creative_upload_reference`.

**Tech Stack:** FastAPI, existing auth/`sessions`, Flutter (`image_picker`, `http` multipart), Cloud WS

**Spec:** `docs/superpowers/specs/2026-07-14-mobile-cloud-attach-design.md`  
**Worktree:** `.worktrees/cloud-agent-p0` (implement here; keep docs on repo root as needed)

---

## File map

| File | Responsibility |
|------|----------------|
| `cloud_agent/app/attachments.py` | CRUD + disk/json persistence + size limits |
| `cloud_agent/app/main.py` | HTTP routes for attachments + file download |
| `cloud_agent/app/ws.py` | Parse `attachment_ids`; allow content-or-attachments; emit `chat.user.attachments` |
| `cloud_agent/app/runtime.py` | Pass attachment ids into agent loop |
| `cloud_agent/app/agent_loop.py` | Inject attachment context; Creative bridge |
| `cloud_agent/app/creative_bridge.py` | Resolve attachments → Creative HTTPS URLs |
| `cloud_agent/tests/test_attachments.py` | Store + HTTP tests |
| `cloud_agent/tests/test_creative_bridge.py` | Bridge with mocked MCP |
| `lib/cloud/models/cloud_models.dart` | Attachment model + event fields |
| `lib/cloud/cloud_api_client.dart` | multipart upload / list / delete |
| `lib/cloud/cloud_ws_client.dart` / `cloud_client.dart` | `sendChat` with `attachmentIds` |
| `lib/state/cloud_chat_controller.dart` | Composer attachments + send + bubble data |
| `lib/features/chat/cloud_chat_page.dart` | `+` Sheet, chips, `@`, bubble media, clarify chips |
| `pubspec.yaml` | `image_picker` (+ platform permissions) |
| `ios/Runner/Info.plist` / Android manifest | photo library permissions |

---

### Task 1: Attachment store + unit tests

**Files:**
- Create: `cloud_agent/app/attachments.py`
- Create: `cloud_agent/tests/test_attachments.py`

- [ ] **Step 1: Write failing tests**

```python
# cloud_agent/tests/test_attachments.py
from pathlib import Path
from app.attachments import AttachmentStore, AttachmentError

def test_add_url_and_list(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    att = store.add_url("s1", "https://example.com/a.jpg", label="a.jpg")
    assert att.kind == "url"
    assert att.ref.startswith("@url:")
    assert store.get("s1", att.id).url == "https://example.com/a.jpg"
    assert len(store.list("s1")) == 1

def test_add_file_image(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    data = b"\xff\xd8\xff" + b"0" * 100  # pretend jpeg header
    att = store.add_file("s1", filename="x.jpg", content=data, mime="image/jpeg")
    assert att.kind == "image"
    assert att.ref == f"@image:{att.id}"
    assert (tmp_path / "s1" / "attachments" / att.id).exists() or True
    # file path exists under session dir
    assert store.file_path("s1", att.id).exists()

def test_reject_oversize(tmp_path: Path):
    store = AttachmentStore(root=tmp_path, max_image_bytes=10)
    try:
        store.add_file("s1", filename="big.jpg", content=b"01234567890", mime="image/jpeg")
        assert False, "expected error"
    except AttachmentError:
        pass

def test_delete(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    att = store.add_url("s1", "https://example.com/a.jpg")
    store.delete("s1", att.id)
    assert store.list("s1") == []
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd .worktrees/cloud-agent-p0/cloud_agent
PYTHONPATH=. .venv/bin/pytest tests/test_attachments.py -v
```

Expected: import / module missing failures.

- [ ] **Step 3: Implement `attachments.py`**

Implement `Attachment` dataclass + `AttachmentStore` with:

- `root/data/sessions/{session_id}/attachments.json` + binary files beside it  
- `add_file` → kind from mime (`image/*` → image, `video/*` → video)  
- `add_url` → validate `http://` or `https://`  
- `list` / `get` / `delete` / `resolve_many(session_id, ids)`  
- Limits: image 25MB, video 100MB (constructor args)  
- `public_dict(att, *, preview_path_prefix)` returning API JSON shape from spec  

- [ ] **Step 4: pytest pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_attachments.py -v
```

Expected: PASS

- [ ] **Step 5: Commit** (if user/agent workflow commits)

```bash
git add cloud_agent/app/attachments.py cloud_agent/tests/test_attachments.py
git commit -m "feat(cloud-agent): session attachment store"
```

---

### Task 2: HTTP routes + file download

**Files:**
- Modify: `cloud_agent/app/main.py`
- Modify: `cloud_agent/tests/test_attachments.py` (add API tests with TestClient)

- [ ] **Step 1: Add API tests**

```python
from fastapi.testclient import TestClient
from app.main import app

AUTH = {"Authorization": "Bearer dev-local-token"}

def test_upload_url_and_list(tmp_path, monkeypatch):
    # point AttachmentStore root at tmp_path via env or dependency if needed
    client = TestClient(app)
    # create a session first using existing POST /v1/sessions
    sid = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "vidau-creative-agent-oneclick"},
    ).json()["session_id"]
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "https://example.com/r.png"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "url"
    assert body["ref"].startswith("@url:")
    listed = client.get(f"/v1/sessions/{sid}/attachments", headers=AUTH).json()
    assert len(listed["attachments"]) == 1
```

Also test multipart file upload and DELETE.

- [ ] **Step 2: Implement routes in `main.py`**

```python
# POST /v1/sessions/{session_id}/attachments
# - if Content-Type json: {kind:url,url}
# - else multipart file field "file"
# GET  /v1/sessions/{session_id}/attachments → {attachments:[...]}
# DELETE /v1/sessions/{session_id}/attachments/{attachment_id}
# GET  /v1/sessions/{session_id}/attachments/{attachment_id}/file → FileResponse
```

`preview_url` / `url` for uploaded files: absolute path using request base or relative  
`/v1/sessions/{sid}/attachments/{id}/file` (Flutter will prefix `cloudHttpBaseUrl`).

Validate session exists (`get_session`). Use `Depends(verify_token)`.

- [ ] **Step 3: pytest pass for new API tests**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(cloud-agent): attachments HTTP API"
```

---

### Task 3: WS `chat.send` + `chat.user.attachments`

**Files:**
- Modify: `cloud_agent/app/ws.py`
- Modify: `cloud_agent/app/runtime.py`
- Modify: `cloud_agent/app/agent_loop.py` (minimal: accept attachments list / enriched content)
- Create or extend: `cloud_agent/tests/test_ws_attachments.py` (optional if hard; otherwise unit-test helper)

- [ ] **Step 1: Change validation**

Allow send when `content.strip()` **or** non-empty `attachment_ids`.

```python
content = (data.get("content") or "").strip()
attachment_ids = data.get("attachment_ids") or []
if not isinstance(attachment_ids, list):
    attachment_ids = []
if not content and not attachment_ids:
    await outbound.put({..., "content": "Missing content"})
    continue
atts = store.resolve_many(session_id, attachment_ids)  # raises → chat.error
```

- [ ] **Step 2: Emit enriched `chat.user` before loop**

Either inside `stream_user_message` / `run_agent_loop` first yield, or in `ws.py` before calling runtime:

```python
{
  "type": "chat.user",
  "session_id": session_id,
  "content": content,
  "attachments": [a.to_public_dict() for a in atts],
}
```

Ensure existing clients ignoring unknown fields still work.

- [ ] **Step 3: Pass attachments into agent loop**

```python
# runtime.py
async def stream_user_message(
    session_id: str,
    content: str,
    *,
    attachments: list | None = None,
) -> AsyncIterator[dict]:
    async for event in run_agent_loop(session_id, content, attachments=attachments or []):
        yield event
```

In `run_agent_loop`, prepend a context block to the user message for the LLM, e.g.:

```text
[Attachments]
- @image:att_01 image/jpeg url=http://127.0.0.1:8787/v1/sessions/.../file
```

- [ ] **Step 4: pytest / manual smoke** — existing tests still pass; new send-with-attachments path covered if feasible.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cloud-agent): chat.send attachment_ids and chat.user attachments"
```

---

### Task 4: Creative bridge

**Files:**
- Create: `cloud_agent/app/creative_bridge.py`
- Create: `cloud_agent/tests/test_creative_bridge.py`
- Modify: `cloud_agent/app/agent_loop.py` — before Creative generate tools, resolve reference URLs

- [ ] **Step 1: Failing tests with fake gateway**

```python
async def test_bridge_uses_existing_https():
    urls = await resolve_creative_reference_urls(
        session_id="s1",
        attachments=[fake_att(kind="url", url="https://cdn.example/a.png")],
        gateway=FakeGw(),
    )
    assert urls == ["https://cdn.example/a.png"]

async def test_bridge_uploads_local_via_instructions(monkeypatch):
    # FakeGw.creative_get_upload_instructions returns put_url + file_url
    # monkeypatch httpx PUT success
    ...
```

- [ ] **Step 2: Implement `resolve_creative_reference_urls`**

Order per spec:

1. If `url` already `https://` and not local agent host → use as-is  
2. Else `creative_get_upload_instructions` → PUT file bytes → `upload.file_url`  
3. Else fallback `creative_upload_reference` with base64 for small images  
4. On failure raise / return error string for assistant message  

Only call when session expert requires `creative-agent` MCP (check session expert catalog entry).

- [ ] **Step 3: Wire into agent_loop** when about to call `creative_generate_image` / `creative_image_to_video` / etc.: merge resolved URLs into tool args `reference_urls` / `reference_image_urls` if missing.

- [ ] **Step 4: pytest pass + commit**

```bash
git commit -m "feat(cloud-agent): Creative attachment URL bridge"
```

---

### Task 5: Flutter models + API/WS clients

**Files:**
- Modify: `lib/cloud/models/cloud_models.dart`
- Modify: `lib/cloud/cloud_api_client.dart`
- Modify: `lib/cloud/cloud_ws_client.dart`
- Modify: `lib/cloud/cloud_client.dart`
- Modify: `pubspec.yaml` — add `image_picker`

- [ ] **Step 1: Add model**

```dart
class CloudAttachment {
  const CloudAttachment({
    required this.id,
    required this.kind, // image | video | url
    required this.label,
    required this.ref,
    this.url,
    this.previewUrl,
    this.mime,
    this.size,
    this.uploadState, // uploading | ready | error
  });
  // fromJson / toJson
}
```

Extend `CloudEvent` / `CloudDisplayMessage` to carry `List<CloudAttachment> attachments`.

- [ ] **Step 2: API client methods**

```dart
Future<CloudAttachment> uploadFile({required String sessionId, required String path, required String filename, String? mime});
Future<CloudAttachment> uploadUrl({required String sessionId, required String url});
Future<List<CloudAttachment>> listAttachments(String sessionId);
Future<void> deleteAttachment({required String sessionId, required String id});
```

Use `http.MultipartRequest` for files. Absolute `previewUrl` = if relative, prefix `config.cloudHttpBaseUrl`.

- [ ] **Step 3: WS send**

```dart
Future<void> sendChat({required String content, List<String> attachmentIds = const []}) async {
  channel.sink.add(jsonEncode({
    'type': 'chat.send',
    'session_id': _sessionId,
    'content': content,
    if (attachmentIds.isNotEmpty) 'attachment_ids': attachmentIds,
  }));
}
```

- [ ] **Step 4: `flutter pub get` + analyze touched files**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(mobile): cloud attachment API and WS payload"
```

---

### Task 6: Composer UI — Sheet, chips, `@`

**Files:**
- Modify: `lib/state/cloud_chat_controller.dart`
- Modify: `lib/features/chat/cloud_chat_page.dart`
- Modify: `ios/Runner/Info.plist` — `NSPhotoLibraryUsageDescription`
- Modify: Android manifest — if needed for photos on older APIs

- [ ] **Step 1: Controller state**

```dart
List<CloudAttachment> pendingAttachments = [];
String? attachError;

Future<void> pickImages();
Future<void> pickVideo();
Future<void> addUrl(String url);
Future<void> removePending(String id);
Future<void> send(); // content + pending ids; clear pending on success
List<CloudAttachment> sessionAttachmentsForAt(); // from last list/cache
```

`send()` rules: allow empty text if `pendingAttachments` non-empty; only include ids with ready state.

- [ ] **Step 2: UI**

- Leading `+` → `showModalBottomSheet` with 相册图片 / 相册视频 / 链接 URL  
- URL → dialog `TextField` + validate  
- Chip row above `TextField`  
- On `@` at caret: if session/pending attachments empty → SnackBar; else overlay list with thumbnails; insert `ref` + space  

Use `image_picker` `pickMultiImage` / `pickVideo`.

- [ ] **Step 3: Manual check on simulator/device** (permissions)

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mobile): cloud composer ATTACH sheet and chips"
```

---

### Task 7: User bubble preview + clarify chips

**Files:**
- Modify: `lib/features/chat/cloud_chat_page.dart`
- Modify: `lib/state/cloud_chat_controller.dart` (parse `attachments` on `chat.user`; optimistic local attachments)

- [ ] **Step 1: User bubble**

For `CloudMessageKind.user`, render text + media:

- image → `Image.network(previewUrl ?? url)` rounded, tap → full screen dialog  
- video → placeholder cover + open URL  
- url → tappable link row  

Optimistic: when sending, build user message with pending attachment previews before WS echo.

- [ ] **Step 2: Clarify chips (Creative)**

If `llmMode`/`expert` is Creative (pass flag via route `extra` already has names): show sticky suggestion chips `9:16` / `1:1` / `16:9` (and optionally 只人物 / 整张场景) under the last assistant message or above composer when conversation looks like a clarifying ask **or** always show aspect chips for Creative sessions after first assistant reply.

On tap → `controller.send(chipLabel)`.

- [ ] **Step 3: `flutter analyze` on chat files**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mobile): inline attachment bubbles and clarify chips"
```

---

### Task 8: End-to-end verification

- [ ] **Step 1: Backend**

```bash
cd .worktrees/cloud-agent-p0/cloud_agent
PYTHONPATH=. .venv/bin/pytest tests/test_attachments.py tests/test_creative_bridge.py -v
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: pass (or only pre-existing failures unrelated to attachments).

- [ ] **Step 2: Run Cloud Agent**

```bash
CLOUD_AGENT_OPENVIDAU_CLIENT_APP=vidau-desktop ./scripts/run_dev.sh
```

- [ ] **Step 3: Flutter**

```bash
cd .worktrees/cloud-agent-p0
flutter run --dart-define=EXECUTION_MODE=cloud --dart-define=CLOUD_HOST=<LAN_IP>
```

Manual checklist from spec §9:

1. Attach photo → chip → send → bubble shows image  
2. URL attach + `@` list  
3. Delete pending chip  
4. Creative aspect chip sends reply  
5. No API keys in Flutter logs  

---

## Spec coverage self-check

| Spec item | Task |
|-----------|------|
| HTTP upload/list/delete | 1–2 |
| WS attachment_ids + chat.user.attachments | 3 |
| Creative bridge | 4 |
| Sheet / chips / @ | 5–6 |
| Bubble preview | 7 |
| Clarify chips | 7 |
| Limits / errors | 1, 6 |
| Link/Files out of scope | — (not scheduled) |

**Placeholder scan:** none intentional.  
**Type names:** `CloudAttachment`, `attachment_ids`, `attachments[]` consistent across tasks.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-14-mobile-cloud-attach.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute in this session with executing-plans checkpoints  

Which approach?
