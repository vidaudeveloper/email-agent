# Cloud Chat 时间线：MCP 步骤 + 历史回看 + 媒体占位 + 详情页

**日期：** 2026-07-14（修订：同日补充 Markdown / Manus 展示 / 详情下载）  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（Creative 会话时间线）  
**工作树：** `.worktrees/cloud-agent-p0`（`feature/cloud-agent-p0`）

**关联文档：**

- [Cloud Chat 问答 + 媒体加载 UX](./2026-07-14-cloud-chat-qa-media-ux-design.md) — 实时 Shimmer / Phase（本文补齐落库与步骤）
- [媒体生成实时进度](./2026-07-11-cloud-agent-media-progress-design.md) — `media.*` 协议（P0 曾不做历史回放；本文解除该限制）
- [会话云存储与历史](./2026-07-14-mobile-cloud-session-history-design.md) — 文本历史；本文扩展 timeline

**视觉参考：** Manus 对话方案（结构化助手正文、步骤条、媒体占位与结果卡）；不照搬任务 4/5 编排引擎与底部悬浮条。

---

## 1. 目标

1. **MCP 步骤从第一步可见**：`tool.mcp` `phase=start` 即出现在流内步骤条。  
2. **历史可回看**：重开会话能看到步骤摘要与已生成图片/视频。  
3. **占位始终在**：Creative 生成前、生成中、结果网络加载中、URL 失效、失败时，媒体区域不塌成空白。  
4. **展示对齐 Manus + Markdown**：助手正文按 Markdown 渲染（标题、列表、加粗等）。  
5. **媒体详情页**：点击图片/视频进入详情，支持预览与**下载**到本地。

### 1.1 已锁定决策

| 议题 | 决策 |
|------|------|
| 架构 | **时间线落库**（步骤 + 媒体 + 文本统一可回放） |
| 历史步骤 UI | **默认折叠**；用户可点开展开 |
| 实时步骤 UI | 当前回合**默认展开**（保证第一步立刻可见） |
| 助手正文 | **Markdown** 渲染（对齐 Manus 结构化阅读体验） |
| Creative 媒体占位 | **生成前 + 生成中 + 显示加载前** 全程占位 |
| 媒体详情 | 全屏/路由详情页；支持下载 |
| 底部悬浮条 | **不做**（沿用上一轮产品决策） |
| 进度历史 | 历史只存媒体终态；不回放每一帧 `media.progress` |

### 1.2 明确不做（本期）

- Manus 完整「任务进度 4/5」多阶段编排引擎  
- 恢复底部悬浮 Phase 条  
- Link 模式同步改造  
- 历史中逐帧回放生成百分比动画  
- 详情页内复杂编辑 / 二次生成工作台  
- 云端对象永久归档（下载到手机相册/文件即可）  

---

## 2. 现状缺口

| 能力 | 现状 | 缺口 |
|------|------|------|
| MCP 步骤 | 后端已发 `tool.mcp` start/end | Flutter 为问答净化而丢弃，第一步不可见 |
| 媒体历史 | `media.ready` 仅 WS | 未入 SQLite；重开只有文本 |
| 占位 | 实时 Shimmer 有 | 历史无卡；`Image.network` 加载/失败时易空白 |
| 助手正文 | 纯 `Text` | 无 Markdown（列表/加粗等） |
| 媒体详情 / 下载 | 无专用页；`url_launcher` 未接 | 缺详情页与保存到本地 |

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

## 4. Flutter UX（对齐 Manus 对话呈现）

整体信息架构对齐 Manus **对话方案**（非其完整 Agent 工作台）：

```text
用户气泡（右）
助手 Markdown 正文（左，结构化可读）
可折叠 MCP 步骤条（完成勾 / 进行中点）
媒体占位 → 结果缩略图/封面（可点进详情）
```

### 4.1 助手正文：Markdown

- `assistant` 消息用 Markdown 渲染（推荐 `flutter_markdown`）。  
- 支持：标题、加粗、有序/无序列表、行内代码、链接（可点外开）。  
- **用户气泡**仍纯文本。  
- 历史与实时共用同一渲染组件；不启用原始 HTML。

### 4.2 实时：MCP 步骤卡

- 监听 `tool.mcp`：`start` → 追加进行中行；`end` → 打勾。  
- **第一步 `start` 立刻渲染**，不等待 `end` 或 `media.*`。  
- 友好名映射（如 `creative_generate_image` →「生成图片」）。  
- 不把 `LLM turn 1/8` 等 `chat.progress` 原文塞进主列表。  
- 当前回合步骤卡**默认展开**；视觉为 Manus 式轻量步骤行（不做 4/5 大卡）。

### 4.3 历史：步骤默认折叠

- 标题如「已完成 N 个步骤」；**默认折叠**；点击展开。  
- 含失败步骤时折叠标题可标「含失败」。

### 4.4 Creative 媒体：全程占位（生成前 / 生成中 / 显示前）

| 阶段 | 触发 | UI |
|------|------|-----|
| 生成前 | `media.placeholder`（或媒体工具 start） | 按 `ratio` 的 Shimmer 展位图立刻出现 |
| 生成中 | `media.progress` | 同一占位卡更新 `%` / 文案，尺寸不晃动 |
| 显示前 | `media.ready` 已到，资源仍在下载解码 | 继续同尺寸占位，加载完再淡入 |
| 显示失败 | URL 404 / 解码失败 | 破图占位 + 「无法加载」 |
| 生成失败 | `media.failed` | 错误占位（保留卡位） |
| 历史回放 | timeline `media` | 有 urls 也先占位再出图 |

**硬性要求（CreativeAgent）：** 从「开始生成」到「用户看见清晰图/视频」之间，媒体槽位始终有占位，禁止空白帧。列表卡可点进详情。

### 4.5 图片 / 视频详情页 + 下载

**入口：** 点击会话内媒体卡。  
**路由：** `/cloud-chat/:sessionId/media/:jobId`（或全屏 `Navigator.push`）。

| 能力 | 说明 |
|------|------|
| 图片 | 大图 + 双指缩放（`InteractiveViewer`） |
| 视频 | 封面 + 播放（内嵌或系统播放器；P0 可外开 URL 兜底） |
| 下载 | 「下载」保存到相册/文件；权限拒绝时 SnackBar 引导 |
| 失败 | 详情内仍占位 + 错误；下载禁用或提示失败 |
| 多 URL | 详情内 PageView 切换 |

**依赖：** `flutter_markdown`；下载用 `http` + `path_provider` / `gal`（或等价，实现计划锁定一种）；视频 P0 可 `url_launcher` 外开 + 仍提供下载。

### 4.6 `start()` 流程

```text
1) GET timeline
2) 按序填入（步骤默认 collapsed；assistant 走 Markdown）
3) WS connect
4) 实时事件 upsert
5) 点击媒体 → MediaDetailPage（可下载）
```

---

## 5. 错误与边界

| 场景 | 行为 |
|------|------|
| 旧会话无 steps/media 表数据 | 仅 Markdown 文本；不报错 |
| `media.ready` 后 WS 断线 | 已落库，重开可回看 |
| 同 `job_id` 重复 ready | upsert 覆盖 |
| 步骤 start 无 end（进程杀） | 历史显示 `running` 或标「未完成」 |
| 下载无权限 / 失败 | 详情页可读错误，不静默失败 |
| Markdown 极长 | 正常滚动；不阻塞媒体卡 |

---

## 6. 实现草图（文件）

**Backend**

- `cloud_agent/app/sessions.py` — 表迁移、`add_step` / `upsert_media`、timeline  
- `cloud_agent/app/agent_loop.py` / `ws.py` / `media_tracker.py` — 事件落库  
- `cloud_agent/app/main.py` — timeline 路由  
- tests：`test_timeline.py`

**Flutter**

- `cloud_models.dart` — timeline item  
- `cloud_api_client.dart` / `cloud_client.dart` — 拉 timeline  
- `cloud_chat_controller.dart` — 回填；`tool.mcp` → 步骤卡  
- `widgets/mcp_steps_card.dart` — Manus 风格步骤条  
- `widgets/assistant_markdown.dart` — 助手 Markdown  
- `media_job_card.dart` — 全程占位 + 进详情  
- `features/chat/media_detail_page.dart` — 图/视频详情 + 下载  
- `app.dart` / go_router — 详情路由  
- `pubspec.yaml` — markdown + 下载/相册依赖  

---

## 7. 验收清单

1. 第一个 `tool.mcp start` 即出现步骤行。  
2. Creative：生成前 / 中 / 显示前全程有展位图，无空白帧。  
3. 助手列表/加粗等按 Markdown 显示（Manus 式阅读感）。  
4. 点击媒体进详情可预览；「下载」可保存到本地。  
5. 重开会话：步骤默认折叠 + 媒体卡（加载前占位）。  
6. URL 404 / 失败有占位；无底部悬浮条；纯文本无步骤噪音。  

---

## 8. 决策记录

| 决策 | 选择 |
|------|------|
| 架构 | 时间线落库 |
| 历史步骤 | 默认折叠 |
| 实时步骤 | 默认展开；第一步即显示 |
| 助手正文 | Markdown |
| 视觉 | 参考 Manus 对话方案 |
| Creative 占位 | 生成前 / 中 / 显示前全程占位 |
| 详情页 | 图/视频详情 + 下载 |
| 悬浮条 | 不做 |
| 进度历史 | 只存终态 |
