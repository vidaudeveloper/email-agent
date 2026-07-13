# Cloud Agent Media Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream Creative MCP generation progress over WebSocket and show Shimmer placeholder cards in Flutter chat that update to real media.

**Architecture:** Parse Creative tool results in `agent_loop`; emit `media.*` events; `MediaJobTracker` polls `creative_get_job` and pushes via a session `MediaHub` bound to the live WebSocket. Flutter upserts media cards by `job_id`.

**Tech Stack:** FastAPI / asyncio, existing MCP gateway, Flutter chat UI

**Worktree:** `.worktrees/cloud-agent-p0`

---

## File map

| File | Responsibility |
|---|---|
| `cloud_agent/app/media_parse.py` | Tool classification + MCP result parsing |
| `cloud_agent/app/media_tracker.py` | Async job polling + emit |
| `cloud_agent/app/media_hub.py` | session_id → async emit callback |
| `cloud_agent/app/agent_loop.py` | Emit placeholder / ready / register tracker |
| `cloud_agent/app/ws.py` | Bind MediaHub for connection lifetime |
| `cloud_agent/tests/test_media_parse.py` | Unit tests for parse/classify |
| `cloud_agent/tests/test_media_tracker.py` | Tracker with mock gateway |
| `lib/cloud/models/cloud_models.dart` | media.* event types + fields |
| `lib/state/cloud_chat_controller.dart` | Media card state machine |
| `lib/features/chat/cloud_chat_page.dart` | Shimmer placeholder + image/video UI |

---

### Task 1: media_parse + tests

**Files:**
- Create: `cloud_agent/app/media_parse.py`
- Create: `cloud_agent/tests/test_media_parse.py`

- [ ] **Step 1: Write failing tests** for `classify_media_tool`, `parse_media_result`, `normalize_tool_suffix`
- [ ] **Step 2: Implement `media_parse.py`**
- [ ] **Step 3: pytest pass**

### Task 2: media_hub + media_tracker + tests

**Files:**
- Create: `cloud_agent/app/media_hub.py`
- Create: `cloud_agent/app/media_tracker.py`
- Create: `cloud_agent/tests/test_media_tracker.py`

- [ ] **Step 1: Implement hub** (`bind` / `unbind` / `emit`)
- [ ] **Step 2: Implement tracker** (4s poll, 15min timeout, progress mapping)
- [ ] **Step 3: Unit test tracker with fake `call_tool`**

### Task 3: Wire agent_loop + ws

**Files:**
- Modify: `cloud_agent/app/agent_loop.py`
- Modify: `cloud_agent/app/ws.py`

- [ ] **Step 1: Before MCP call** — if media tool → `media.placeholder`
- [ ] **Step 2: After result** — sync ready/failed or `tracker.track(...)`
- [ ] **Step 3: ws binds MediaHub emit on accept; unbind on disconnect**
- [ ] **Step 4: Existing pytest suite still passes**

### Task 4: Flutter models + controller + UI

**Files:**
- Modify: `lib/cloud/models/cloud_models.dart`
- Modify: `lib/state/cloud_chat_controller.dart`
- Modify: `lib/features/chat/cloud_chat_page.dart`

- [ ] **Step 1: Add CloudEventType media\*** + fields (`jobId`, `kind`, `progress`, `urls`, `error`, `ratio`, `label`)
- [ ] **Step 2: Controller upserts media messages; chat.done does not clear them**
- [ ] **Step 3: UI Shimmer card + network image / video link**
- [ ] **Step 4: `flutter analyze` on touched files**

### Task 5: Smoke verification

- [ ] **Step 1: pytest media + agent tests**
- [ ] **Step 2: Manual note for device: restart server, ask generate image**

---

## Spec coverage

| Spec requirement | Task |
|---|---|
| media.* protocol | 1–4 |
| MediaJobTracker 4s / 15min | 2 |
| White-list Creative tools | 1, 3 |
| WS after chat.done | 2–3 (hub) |
| Flutter Shimmer + % | 4 |
| No client HTTP poll | ✓ by design |
