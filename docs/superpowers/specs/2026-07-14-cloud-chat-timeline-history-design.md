# Cloud Chat 时间线：MCP 步骤 + 历史回看 + 媒体占位

**日期：** 2026-07-14  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（会话时间线）  
**工作树：** `.worktrees/cloud-agent-p0`（`feature/cloud-agent-p0`）

**关联文档：**

- [Cloud Chat 问答 + 媒体加载 UX](./2026-07-14-cloud-chat-qa-media-ux-design.md) — 实时 Shimmer / Phase（本文补齐落库与步骤）
- [媒体生成实时进度](./2026-07-11-cloud-agent-media-progress-design.md) — `media.*` 协议（P0 曾不做历史回放；本文解除该限制）
- [会话云存储与历史](./2026-07-14-mobile-cloud-session-history-design.md) — 文本历史；本文扩展 timeline

---

## 1. 目标

1. **MCP 步骤从第一步可见**：`tool.mcp` `phase=start` 即出现在流内步骤条。  
2. **历史可回看**：重开会话能看到步骤摘要与已生成图片/视频。  
3. **占位始终在**：生成中、网络加载中、URL 失效、失败时，媒体区域不塌成空白。

### 1.1 已锁定决策

| 议题 | 决策 |
|------|------|
| 架构 | **时间线落库**（步骤 + 媒体 + 文本统一可回放） |
| 历史步骤 UI | **默认折叠**；用户可点开展开 |
| 实时步骤 UI | 当前回合**默认展开**（保证第一步立刻可见） |
| 底部悬浮条 | **不做**（沿用上一轮产品决策） |
| 进度历史 | 历史只存媒体终态；不回放每一帧 `media.progress` |

### 1.2 明确不做（本期）

- Manus 完整「任务进度 4/5」多阶段编排引擎  
- 恢复底部悬浮 Phase 条  
- Link 模式同步改造  
- 历史中逐帧回放生成百分比动画  

---

## 2. 现状缺口

| 能力 | 现状 | 缺口 |
|------|------|------|
| MCP 步骤 | 后端已发 `tool.mcp` start/end | Flutter 为问答净化而丢弃，第一步不可见 |
| 媒体历史 | `media.ready` 仅 WS | 未入 SQLite；重开只有文本 |
| 占位 | 实时 Shimmer 有 | 历史无卡；`Image.network` 加载/失败时易空白 |

---

## 3. 数据模型

### 3.1 新表（推荐）

**`session_steps`**

| 列 | 说明 |
|----|------|
| `id` | PK |
| `session_id` | 会话 |
| `turn_id` | 可选；同一用户回合内步骤分组（可用 user message id 或 ISO 批次） |
| `tool` | 原始工具名 |
| `label` | 友好名（服务端或客户端映射） |
| `status` | `running` \| `done` \| `failed` |
| `started_at` / `ended_at` | 时间 |

**`session_media`**

| 列 | 说明 |
|----|------|
| `id` | PK |
| `session_id` | 会话 |
| `job_id` | 与 WS `media.*` 对齐，唯一 |
| `kind` | `image` \| `video` \| `audio` \| `other` |
| `state` | `pending` \| `generating` \| `ready` \| `failed` |
| `urls_json` | JSON 数组 |
| `thumbnail_url` | 可选 |
| `ratio` | 可选 |
| `error` | 可选 |
| `label` | 可选 |
| `created_at` / `updated_at` | 时间 |

现有 `messages`（user/assistant 文本）不变。

### 3.2 写入时机

| 事件 | 写入 |
|------|------|
| `tool.mcp` phase=start | upsert step `running`（**第一步即落库/推 UI**） |
| `tool.mcp` phase=end | step → `done`（工具抛错则 `failed`） |
| `media.placeholder` | upsert media `pending` |
| `media.progress` | 更新 state/progress 字段（progress 可只留内存；历史可不存） |
| `media.ready` | media → `ready` + urls |
| `media.failed` | media → `failed` + error |

### 3.3 历史 API

扩展 `GET /v1/sessions/{id}/messages` 为 timeline，**或**新增：

- `GET /v1/sessions/{id}/timeline`

响应示例（交错）：

```json
{
  "items": [
    { "type": "message", "role": "user", "content": "…", "created_at": "…" },
    { "type": "steps", "turn_id": "…", "collapsed_default": true, "steps": [
      { "tool": "creative_generate_image", "label": "生成图片", "status": "done" }
    ]},
    { "type": "media", "job_id": "…", "kind": "image", "state": "ready",
      "urls": ["https://…"], "ratio": "1:1" },
    { "type": "message", "role": "assistant", "content": "…", "created_at": "…" }
  ]
}
```

向后兼容：旧客户端仍可只读 `messages`；新 Flutter 走 timeline。

---

## 4. Flutter UX

### 4.1 实时：MCP 步骤卡

- 监听 `tool.mcp`：`start` → 在当前回合步骤卡追加一行（进行中）；`end` → 打勾。  
- **第一步 `start` 必须立刻渲染**，不等待 `end` 或 `media.*`。  
- 友好名映射与媒体 UX 共用（如 `creative_generate_image` →「生成图片」）。  
- 仍不把 `LLM turn 1/8` 等 `chat.progress` 原文塞进主列表。  
- 当前进行中的回合：步骤卡**默认展开**。

### 4.2 历史：步骤默认折叠

- 回放时每个 `steps` 块渲染为可折叠卡片，标题如「已完成 N 个步骤」。  
- **默认折叠**（已锁定）；点击展开看完整列表。  
- 失败步骤在折叠标题上可用小红点/「含失败」提示。

### 4.3 媒体卡 + 占位

| 状态 | UI |
|------|-----|
| pending / generating | Shimmer 占位（按 `ratio`）+ 文案 |
| ready，图片加载中 | 同尺寸占位，`Image.network` 加载完替换 |
| ready，加载失败 | 破图占位 +「无法加载」 |
| failed | 错误占位（保留卡位） |
| 历史 ready | 直接媒体卡；加载前仍先占位 |

历史回填：`state=ready` 且有 urls → 媒体卡；若仅有 failed → 错误占位；不应出现「有过生成但完全空白」。

### 4.4 `start()` 流程

```text
1) GET timeline（或 messages + steps + media）
2) 按序填入 transcript（步骤块默认 collapsed=true）
3) WS connect
4) 后续实时事件 upsert（同 job_id / turn 合并）
```

---

## 5. 错误与边界

| 场景 | 行为 |
|------|------|
| 旧会话无 steps/media 表数据 | 仅文本；不报错 |
| `media.ready` 后 WS 断线 | 已落库，重开可回看 |
| 同 `job_id` 重复 ready | upsert 覆盖 |
| 步骤 start 无 end（进程杀） | 历史显示 `running` 或打开时标为 `failed`/「未完成」 |

---

## 6. 实现草图（文件）

**Backend**

- `cloud_agent/app/sessions.py` — 表迁移、`add_step` / `upsert_media`、timeline 查询  
- `cloud_agent/app/agent_loop.py` / `ws.py` / `media_tracker.py` — 事件时落库  
- `cloud_agent/app/main.py` — timeline 路由  
- tests：`test_timeline.py`

**Flutter**

- `cloud_models.dart` — timeline item 模型  
- `cloud_api_client.dart` / `cloud_client.dart` — 拉 timeline  
- `cloud_chat_controller.dart` — 回填；恢复 `tool.mcp` → 步骤卡  
- `widgets/mcp_steps_card.dart` — 展开/折叠步骤  
- `media_job_card.dart` — 强化 loading/error 占位  

---

## 7. 验收清单

1. 发起生成：步骤卡在**第一个** `tool.mcp start` 即出现「生成图片」等行。  
2. 生成中：Shimmer 占位；可上滑浏览；无底部悬浮条。  
3. `media.ready` 后见图片；杀 App 重开同一会话：见折叠步骤条 + 图片卡。  
4. 历史步骤**默认折叠**，点击可展开。  
5. 图片 URL 慢加载或 404：始终有占位，不出现大块空白。  
6. 纯文本问答：无步骤卡噪音（无 MCP 调用时）。  

---

## 8. 决策记录

| 决策 | 选择 |
|------|------|
| 架构 | 时间线落库 |
| 历史步骤 | 默认折叠 |
| 实时步骤 | 默认展开；第一步即显示 |
| 悬浮条 | 不做 |
| 进度历史 | 只存终态 |
