# Vidau Cloud Agent P0（本机可跑）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本机部署 Cloud Agent 服务端（Catalog + Session + Runtime + MCP Gateway），Flutter 以「云端模式」选 Expert 并完成至少 1 条真实/可切换 mock 的 MCP 调用闭环；沙箱仅保留接口，默认 `none`。

**Architecture:** 新建 `cloud_agent/`（FastAPI + WSS）跑在开发机；复用桌面 `experts/catalog.json` 概念做精简 Catalog；Agent Runtime 组装 activation_prompt + skills，经 MCP Gateway 调远程 MCP（开发可 `MCP_MODE=mock`）。Flutter 增加 `ExecutionMode.cloud`，与现有 Mobile Link 模式并存。Sandbox Provider 抽象预留，P0 固定 `none`。

**Tech Stack:** Python 3.11+、FastAPI、uvicorn、httpx、websockets、SQLite；Flutter 现有工程；可选对接真实 TikTok Ads MCP URL。

**Spec:** [2026-07-11-vidau-cloud-agent-design.md](../specs/2026-07-11-vidau-cloud-agent-design.md)  
**范围：** 仅 **P0 + Dev Profile**（本机）。不含 Firecracker、不含 browser 沙箱、不含生产多租户。

**默认锁定（本计划）：**

| 项 | 值 |
|---|---|
| 首发 Expert | `tiktok-ads-agent` |
| Sandbox | `none`（接口预留） |
| MCP | `mock` 默认可演示；`real` 需配置 URL + API Key |
| 仓库布局 | 服务端放在本仓 `cloud_agent/`，便于本机一键起 |

---

## 文件结构（将创建 / 修改）

```text
mobile_agent/
  cloud_agent/
    pyproject.toml                 # 或 requirements.txt
    README.md                      # 本机启动说明
    app/
      main.py                      # FastAPI 入口
      config.py                    # env：MCP_MODE, CATALOG_PATH, …
      auth.py                      # 开发用 JWT / 固定 dev token
      catalog.py                   # Expert/Skill 列表与状态
      sessions.py                  # 会话 CRUD + SQLite
      runtime.py                   # 简化 Agent loop（LLM 可选 stub）
      mcp_gateway.py               # mock / real MCP 调用
      sandbox/
        base.py                    # SandboxProvider Protocol
        none.py                    # P0 实现
      ws.py                        # 会话事件推送
      models.py                    # Pydantic 模型
    data/
      catalog.json                 # 精简版（含 tiktok-ads-agent）
    tests/
      test_catalog.py
      test_session_create.py
      test_mcp_gateway.py
      test_ws_flow.py
  lib/
    core/config.dart               # 增加 ExecutionMode.cloud + cloudBaseUrl
    cloud/                         # 新建
      cloud_client.dart
      cloud_api_client.dart
      cloud_ws_client.dart
      models/cloud_models.dart
    features/
      experts/experts_page.dart    # 新建：市场列表
      chat/chat_page.dart          # 支持云端会话
    state/
      cloud_chat_controller.dart   # 新建
      experts_controller.dart      # 新建
    app.dart                       # 路由：云端入口
  test/
    cloud_models_test.dart
    experts_controller_test.dart
```

---

### Task 1: Cloud Agent 骨架与配置

**Files:**
- Create: `cloud_agent/requirements.txt`
- Create: `cloud_agent/app/config.py`
- Create: `cloud_agent/app/main.py`
- Create: `cloud_agent/README.md`
- Test: `cloud_agent/tests/test_health.py`

- [ ] **Step 1: 写失败的健康检查测试**

```python
# cloud_agent/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd cloud_agent && pip install -r requirements.txt && pytest tests/test_health.py -v
```

Expected: FAIL（无 app 或无路由）

- [ ] **Step 3: 最小实现**

`requirements.txt`:

```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
httpx>=0.27.0
pydantic>=2.0
pydantic-settings>=2.0
pytest>=8.0
```

`app/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mcp_mode: str = "mock"  # mock | real
    sandbox_provider: str = "none"
    catalog_path: str = "data/catalog.json"
    sqlite_path: str = "data/sessions.db"
    dev_token: str = "dev-local-token"
    llm_mode: str = "stub"  # stub | openai_compatible
    cors_origins: str = "*"

    class Config:
        env_prefix = "CLOUD_AGENT_"

settings = Settings()
```

`app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="Vidau Cloud Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "ok": True,
        "mcp_mode": settings.mcp_mode,
        "sandbox_provider": settings.sandbox_provider,
    }
```

- [ ] **Step 4: 再跑测试**

```bash
cd cloud_agent && PYTHONPATH=. pytest tests/test_health.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cloud_agent/requirements.txt cloud_agent/app/config.py cloud_agent/app/main.py cloud_agent/tests/test_health.py cloud_agent/README.md
git commit -m "feat(cloud-agent): add FastAPI health skeleton for local P0"
```

---

### Task 2: Catalog（TikTok Ads Expert）

**Files:**
- Create: `cloud_agent/data/catalog.json`
- Create: `cloud_agent/app/catalog.py`
- Create: `cloud_agent/app/models.py`
- Modify: `cloud_agent/app/main.py`
- Test: `cloud_agent/tests/test_catalog.py`

- [ ] **Step 1: 写 Catalog 测试**

```python
# cloud_agent/tests/test_catalog.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_experts_contains_tiktok():
    r = client.get("/v1/experts", headers={"Authorization": "Bearer dev-local-token"})
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()["experts"]]
    assert "tiktok-ads-agent" in ids

def test_expert_status_fields():
    r = client.get("/v1/experts/tiktok-ads-agent", headers={"Authorization": "Bearer dev-local-token"})
    body = r.json()
    assert body["id"] == "tiktok-ads-agent"
    assert "requires_mcp" in body
    assert "tiktok-ads-agent" in body["requires_mcp"]
    assert body["sandbox_policy"] in ("never", "on_demand", "always")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd cloud_agent && PYTHONPATH=. pytest tests/test_catalog.py -v
```

Expected: FAIL（404）

- [ ] **Step 3: 实现 catalog.json + API**

`data/catalog.json`（精简，对齐桌面字段）：

```json
{
  "experts": [
    {
      "id": "tiktok-ads-agent",
      "name": "TikTok Ads Expert",
      "name_i18n": {"zh": "TikTok 广告专家", "en": "TikTok Ads Expert"},
      "description": "Campaign creation, inspection, and reports via MCP.",
      "tags": ["TikTok Ads", "MCP"],
      "skills": ["tiktok-ads-skills"],
      "toolsets": ["web", "file", "terminal"],
      "requires_mcp": ["tiktok-ads-agent"],
      "sandbox_policy": "on_demand",
      "activation_prompt": "You are the TikTok Ads Expert. Use tiktok-ads-agent MCP tools for campaigns, inspection, and reports. Present data in tables."
    }
  ],
  "skills": [
    {
      "id": "tiktok-ads-skills",
      "name": "tiktok-ads-skills",
      "description": "Playbook for TikTok ads workflows.",
      "requires_mcp": ["tiktok-ads-agent"],
      "body": "When managing TikTok ads, prefer MCP tools create_campaign, create_adgroup, create_ad, and inspection/report tools. Ask for missing account or budget parameters."
    }
  ]
}
```

`app/catalog.py`：加载 JSON；`list_experts` / `get_expert`；开发态若未配置 MCP 凭证则 `status=needs_setup`，mock 模式下可直接 `ready`。

`GET /v1/experts`、`GET /v1/experts/{id}`；鉴权：`Authorization: Bearer <CLOUD_AGENT_DEV_TOKEN>`。

- [ ] **Step 4: 测试通过并 Commit**

```bash
cd cloud_agent && PYTHONPATH=. pytest tests/test_catalog.py -v
git add cloud_agent/data/catalog.json cloud_agent/app/catalog.py cloud_agent/app/models.py cloud_agent/app/main.py cloud_agent/tests/test_catalog.py
git commit -m "feat(cloud-agent): add expert catalog API with tiktok-ads-agent"
```

---

### Task 3: MCP Gateway（mock + real 开关）

**Files:**
- Create: `cloud_agent/app/mcp_gateway.py`
- Create: `cloud_agent/app/credentials.py`
- Test: `cloud_agent/tests/test_mcp_gateway.py`

- [ ] **Step 1: 写 Gateway 测试**

```python
import pytest
from app.mcp_gateway import McpGateway
from app.config import Settings

@pytest.mark.asyncio
async def test_mock_list_and_call_tool():
    gw = McpGateway(Settings(mcp_mode="mock"))
    tools = await gw.list_tools("tiktok-ads-agent")
    names = [t["name"] for t in tools]
    assert "mcp_tiktok-ads-agent_create_campaign" in names or any("create_campaign" in n for n in names)
    result = await gw.call_tool("tiktok-ads-agent", "create_campaign", {"name": "test"})
    assert result["ok"] is True
```

- [ ] **Step 2: 实现**

`McpGateway`：

- `mock`：内置工具表 `create_campaign` / `list_campaigns` / `inspect_ads`，返回固定 JSON。  
- `real`：用 httpx 连 `CLOUD_AGENT_MCP_TIKTOK_URL`（SSE 或 HTTP，按现网 MCP 协议最小实现；若协议复杂，P0 real 可先只做 HTTP JSON-RPC 子集并在 README 注明）。  
- `credentials.py`：内存/SQLite 存 `user_id → {server: api_key}`；`PUT /v1/credentials/{server}`。

工具名对外统一：`mcp_{server}_{tool}`（与桌面一致）。

- [ ] **Step 3: 测试通过并 Commit**

```bash
cd cloud_agent && PYTHONPATH=. pytest tests/test_mcp_gateway.py -v
git add cloud_agent/app/mcp_gateway.py cloud_agent/app/credentials.py cloud_agent/tests/test_mcp_gateway.py
git commit -m "feat(cloud-agent): add MCP gateway with mock and real modes"
```

---

### Task 4: Session + Sandbox stub + 简化 Runtime

**Files:**
- Create: `cloud_agent/app/sessions.py`
- Create: `cloud_agent/app/runtime.py`
- Create: `cloud_agent/app/sandbox/base.py`
- Create: `cloud_agent/app/sandbox/none.py`
- Modify: `cloud_agent/app/main.py`
- Test: `cloud_agent/tests/test_session_create.py`

- [ ] **Step 1: 会话创建测试**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-token"}

def test_create_session_with_expert():
    r = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "tiktok-ads-agent"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["status"] == "ready"
    assert body["sandbox"]["provider"] == "none"
    assert body["sandbox"]["allocated"] is False
```

- [ ] **Step 2: 实现**

- SQLite 表：`sessions(id, expert_id, created_at, …)`、`messages(session_id, role, content, ts)`。  
- `POST /v1/sessions`：解析 expert → 加载 skills + activation_prompt → 检查 MCP（mock 下恒 ready）→ **不**调用 sandbox allocate。  
- `SandboxProvider` Protocol：`allocate/pause/destroy`；`NoneSandboxProvider` 全部 no-op 且 `allocated=False`。  
- `runtime.py`（`llm_mode=stub`）：用户消息进来后，若含「创建广告/campaign」等关键词，直接 `mcp_gateway.call_tool(create_campaign)`，再拼一条 assistant 回复；否则回显「已加载 Expert + 可用工具列表」。  
  （真 LLM 留 `llm_mode=openai_compatible` 扩展点，P0 不强制。）

- [ ] **Step 3: 测试通过并 Commit**

```bash
cd cloud_agent && PYTHONPATH=. pytest tests/test_session_create.py -v
git commit -am "feat(cloud-agent): session create with none sandbox and stub runtime"
```

---

### Task 5: WebSocket 事件流

**Files:**
- Create: `cloud_agent/app/ws.py`
- Modify: `cloud_agent/app/runtime.py`、`main.py`
- Test: `cloud_agent/tests/test_ws_flow.py`

- [ ] **Step 1: 定义事件类型（与产品文档对齐）**

```json
{"type": "chat.user", "session_id": "...", "content": "...", "msg_id": "..."}
{"type": "chat.progress", "session_id": "...", "content": "..."}
{"type": "tool.mcp", "session_id": "...", "tool": "mcp_…_create_campaign", "phase": "start|end"}
{"type": "chat.assistant", "session_id": "...", "content": "..."}
{"type": "chat.done", "session_id": "..."}
{"type": "sandbox.status", "session_id": "...", "status": "none"}
```

- [ ] **Step 2: `WS /v1/sessions/{id}/ws?token=…`**

连接后客户端发：`{"type":"chat.send","content":"帮我创建一个测试广告系列"}`  
服务端依次推送 progress → tool.mcp → assistant → done。

- [ ] **Step 3: 用 TestClient/httpx websocket 或 starlette 测试至少收到 `chat.done`**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(cloud-agent): websocket chat event stream for P0"
```

---

### Task 6: 本机启动脚本与 README

**Files:**
- Create: `cloud_agent/scripts/run_dev.sh`
- Modify: `cloud_agent/README.md`

- [ ] **Step 1: `run_dev.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
export CLOUD_AGENT_MCP_MODE="${CLOUD_AGENT_MCP_MODE:-mock}"
export CLOUD_AGENT_SANDBOX_PROVIDER=none
uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload
```

- [ ] **Step 2: README 写明**

- 启动：`./scripts/run_dev.sh`  
- 健康检查：`curl localhost:8787/health`  
- Flutter：`CLOUD_BASE_URL=http://<局域网IP>:8787`  
- 真 MCP：`CLOUD_AGENT_MCP_MODE=real` + URL/Key  
- 沙箱：P0 固定 none；P1 换 docker  

- [ ] **Step 3: Commit**

```bash
git add cloud_agent/scripts/run_dev.sh cloud_agent/README.md
git commit -m "docs(cloud-agent): local run script and README"
```

---

### Task 7: Flutter — Cloud 客户端与模型

**Files:**
- Modify: `lib/core/config.dart`
- Create: `lib/cloud/models/cloud_models.dart`
- Create: `lib/cloud/cloud_api_client.dart`
- Create: `lib/cloud/cloud_ws_client.dart`
- Create: `lib/cloud/cloud_client.dart`
- Test: `test/cloud_models_test.dart`

- [ ] **Step 1: `ExecutionMode { link, cloud }` + `cloudBaseUrl`（默认 `http://127.0.0.1:8787`）**

- [ ] **Step 2: 模型与解析测试**

```dart
test('parse expert list', () {
  final json = {
    'experts': [
      {
        'id': 'tiktok-ads-agent',
        'name': 'TikTok Ads Expert',
        'status': 'ready',
        'requires_mcp': ['tiktok-ads-agent'],
      }
    ]
  };
  final list = ExpertInfo.listFromJson(json);
  expect(list.first.id, 'tiktok-ads-agent');
  expect(list.first.status, ExpertStatus.ready);
});
```

- [ ] **Step 3: `CloudApiClient`：`GET /v1/experts`、`POST /v1/sessions`；`CloudWsClient` 解析事件**

- [ ] **Step 4: `flutter test test/cloud_models_test.dart` 通过并 Commit**

```bash
git add lib/core/config.dart lib/cloud test/cloud_models_test.dart
git commit -m "feat(mobile): add cloud API client and expert models"
```

---

### Task 8: Flutter — Experts 页 + 云端聊天

**Files:**
- Create: `lib/features/experts/experts_page.dart`
- Create: `lib/state/experts_controller.dart`
- Create: `lib/state/cloud_chat_controller.dart`
- Modify: `lib/features/chat/chat_page.dart`（或新建 `cloud_chat_page.dart`）
- Modify: `lib/app.dart`
- Test: `test/experts_controller_test.dart`（可用 mock HTTP）

- [ ] **Step 1: Experts 列表页**

展示 name、status、requires_mcp；点「使用」→ `POST /v1/sessions` → 进入云端聊天页。

- [ ] **Step 2: 云端聊天页**

发送文本 → WS `chat.send`；渲染 `chat.assistant` / `chat.progress` / `tool.mcp`；顶部标明「云端执行」。

- [ ] **Step 3: `app.dart` 增加入口**

首页或抽屉：「链接电脑」(现有) | 「云端 Agent」(新)。

- [ ] **Step 4: 手测清单写入 PR/提交说明**

1. `./cloud_agent/scripts/run_dev.sh`  
2. `flutter run`，选云端 Agent  
3. 选 TikTok Ads Expert → 发「创建一个测试广告系列」  
4. 看到 mock MCP 工具调用与 assistant 回复  

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(mobile): experts market and cloud chat for P0"
```

---

### Task 9: 端到端冒烟（本机）

**Files:**
- Create: `cloud_agent/scripts/smoke_p0.sh`
- Modify: design/plan 无强制改代码

- [ ] **Step 1: smoke 脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://127.0.0.1:8787}"
TOKEN="dev-local-token"
curl -sf "$BASE/health" | grep -q '"ok":true'
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/v1/experts" | grep -q tiktok-ads-agent
SID=$(curl -sf -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"expert_id":"tiktok-ads-agent"}' "$BASE/v1/sessions" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
test -n "$SID"
echo "smoke ok session=$SID"
```

- [ ] **Step 2: 对运行中的服务执行并通过**

```bash
chmod +x cloud_agent/scripts/smoke_p0.sh && ./cloud_agent/scripts/smoke_p0.sh
```

- [ ] **Step 3: Commit**

```bash
git add cloud_agent/scripts/smoke_p0.sh
git commit -m "test(cloud-agent): add P0 local smoke script"
```

---

## 本计划不包含（后续计划）

| 项 | 计划 |
|---|---|
| `dev_docker` / Firecracker 沙箱 | P1 plan |
| 真 LLM tool loop | P0.5 或并入 P1 |
| Creative Expert | 第二个 Expert 增量 |
| 生产鉴权 / 多租户配额 | 预发 plan |
| Mobile Link 真 Gateway | 已有独立 plan |

---

## Spec 覆盖自检

| Spec 要求 | 本计划 Task |
|---|---|
| 云端执行、不连电脑 | Task 7–8 云端模式 |
| Catalog + TikTok Expert | Task 2 |
| Skill/MCP 声明式绑定 | Task 2–3 |
| MCP Gateway mock/real | Task 3 |
| 会话云端存储 | Task 4 |
| 流式事件 | Task 5 |
| 沙箱按需但 P0 可不开 | Task 4 `none` |
| Dev Profile 本机拓扑 | Task 1、6、9 |
| Flutter 市场 + 聊天 | Task 7–8 |
| Firecracker / 多租户生产 | **故意不含**（P1+） |

---

## 执行方式

Plan 已保存。可选：

1. **Subagent-Driven（推荐）** — 每 Task 派生子代理，Task 间回顾  
2. **Inline Execution** — 本会话按 Task 连续实现并设检查点  

回复选 **1** 或 **2** 即可开始实现。
