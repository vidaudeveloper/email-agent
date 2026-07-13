# Cloud Agent 媒体生成实时进度设计

**日期：** 2026-07-11  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（Creative MCP 生成 UX）  
**工作树：** `.worktrees/cloud-agent-p0`

**关联文档：**

- [Cloud Agent 产品设计](./2026-07-11-vidau-cloud-agent-design.md)
- 桌面 Creative MCP / skill：`~/.vidau/skills/vidau-creative/creative-job-runner`
- 手机端参考 UX：`DemoFile/ai_tools` Agent 聊天（Shimmer 占位 + 进度%）

---

## 1. 目标

Creative Expert 在手机 Cloud Agent 聊天中生成图片 / 视频 / BGM / workflow 等时：

1. **立刻**出现与 ai_tools Agent 聊天一致的 **Shimmer 占位卡**（非 Creation 页 GIF）。
2. 生成过程 **实时**更新进度（百分比 / 状态文案）。
3. 完成后 **原地**换成可预览的图片或视频（多 URL 可多张卡或轮播）。
4. 工具与结果 schema **与桌面 Creative MCP 一致**（同一套 `creative_*` 工具、`job_id`、`artifacts[].urls.download`、`tracking.*`）。

### 1.1 成功标准

- 调用任意白名单媒体工具时，WS 在工具执行前发出 `media.placeholder`。
- 异步 `submit_*`：后端 Tracker 轮询 `creative_get_job`，推送 `media.progress` → `media.ready|failed`；**手机不轮询**。
- 同步 `creative_generate_*`：无真实 job 时用 `local-{tool_call_id}`，返回后直接 `media.ready`。
- Flutter 按 `job_id` 更新同一气泡；`chat.done` 之后仍能收 `media.*`。
- 失败时占位卡变为错误态，文案可读。

### 1.2 明确不做（本阶段）

- Creation 页 `creation_loading.gif` 资源
- 手机端 HTTP `job_ref` 轮询（ai_tools 旧路径）
- 改桌面 Agent / skill 协议
- 会话历史持久化媒体卡片的完整回放（可后续；P0 仅当前连接生命周期 + 可选内存）
- 计费 / VIP 引导 UI（错误文案透传即可）

---

## 2. 与桌面一致性

| 层 | 一致 | 刻意差异 |
|---|---|---|
| MCP URL / 鉴权 | `creative.vidau.info/mcp` + `vidau_user_id` 等与桌面相同 | — |
| 工具名与返回结构 | 同一 Creative 工具集与 artifact / tracking 字段 | — |
| LLM skill「提交后不 sleep/poll」 | LLM 回合仍可不主动轮询 | **基础设施** `MediaJobTracker` 代用户轮询，专供手机实时 UX |
| 聊天视觉 | 结果可展示媒体 | 桌面 TUI 多为链接；手机采用 **ai_tools Shimmer 占位**（产品已选定） |

---

## 3. 架构

```text
Flutter CloudChat
    ↕ WebSocket（已有 + media.*）
cloud_agent agent_loop
    → creative MCP tools
    → 解析 job_id / artifacts / URLs
    → MediaJobTracker（后台 creative_get_job）
    → 推送 media.placeholder|progress|ready|failed
```

**模块职责**

- **agent_loop**：识别媒体工具；发 placeholder；解析 MCP 结果；注册 Tracker 或直接 ready/failed。
- **MediaJobTracker**（新）：按 session 管理多 job；4s 轮询；超时 15min；经 WS 发送队列推事件。
- **Flutter**：`job_id` 状态机 `pending → generating → ready|failed`；Shimmer 占位卡。

---

## 4. WebSocket 事件协议

保留现有：`chat.progress`、`tool.mcp`、`chat.assistant`、`chat.done` 等。

新增：

| type | 时机 | 字段 |
|---|---|---|
| `media.placeholder` | 媒体工具开始前 | `job_id`, `kind` (`image`\|`video`\|`audio`\|`other`), `tool`, `ratio?`, `label?` |
| `media.progress` | Tracker 或心跳 | `job_id`, `progress` (0–100), `status` (`queued`\|`processing`), `message?` |
| `media.ready` | 有可展示结果 | `job_id`, `kind`, `urls` (string[]), `thumbnail_url?`, `message?` |
| `media.failed` | 失败 / 超时 | `job_id`, `error` |

**job_id**

- MCP 返回真实 `job_id` → 使用之。
- 同步无 job → `local-{tool_call_id}`。

**并发**：每次工具调用独立 `job_id`，多卡并存。

**回合后推送**：`chat.done` 之后 Tracker 仍可发 `media.*`；客户端在 `sending=false` 后继续处理。

---

## 5. 后端：工具识别与 Tracker

### 5.1 白名单

| 类别 | 工具（名后缀 / 归一化后） | kind | 行为 |
|---|---|---|---|
| 同步生成 | `creative_generate_image`, `creative_generate_video`, `creative_generate_bgm`, `creative_image_to_video`, `creative_first_frame_to_video`, `creative_mux_bgm_into_video` | image/video/audio | placeholder → 解析 artifacts → ready/failed |
| 异步提交 | `creative_submit_workflow`, `creative_submit_script2film`, `creative_submit_script2film_keyframes`, `creative_submit_batch_variants` | 按工具推断（默认 video；batch 可为 image） | placeholder + 真实 job_id → Tracker |
| 非媒体 UI | `creative_get_job`, `creative_list_jobs`, `creative_cancel_job`, `creative_estimate`, `creative_list_models`, `creative_get_upload_instructions`, `creative_upload_reference`（无 job 时） | — | 仅 `tool.mcp`，不发 placeholder |

名称匹配：对 `mcp_creative-agent_` / `mcp_creative_agent_` 前缀归一化后再匹配上表。

### 5.2 结果解析优先级

1. `job_id`（及 `tracking.should_continue_polling` 等）
2. `artifacts[].urls.download`（及同类 url 字段）
3. `result_urls` / 顶层 `url`
4. MCP `structuredContent` 或 text 块中的 JSON

解析失败 → `media.failed`，原始摘要仍写入 tool message 供 LLM 解释。

### 5.3 MediaJobTracker

- 间隔：**4s**（对齐 ai_tools）
- 超时：**15min**（可配置 `CLOUD_AGENT_MEDIA_JOB_TIMEOUT_MS`）
- 进度：优先 MCP `progress`；否则 `queued→5`，`processing→max(10, n)`，`done→ready`，`failed→failed`
- 完成时提取 `result_urls` / artifacts 下载链 → `media.ready`
- P0 状态存 **进程内存**（按 `session_id`）；WS 重连后可补发该 session 未终结 job 的最新快照（若仍在内存）
- 进程退出则未完成 job 丢失（可接受；后续可持久化）

### 5.4 WS 协作

异步 job 在 agent_loop 的 `yield` 结束后仍需推送：由 `ws.py` 持有 per-connection outbound queue，Tracker 写入同一 queue（与 loop 并行）。

---

## 6. Flutter UI / 状态机

### 6.1 消息模型扩展

`CloudDisplayMessage` 增加媒体字段（或独立 `CloudMediaCard` 列表合并进 transcript）：

- `jobId`, `mediaKind`, `mediaState` (`pending`\|`generating`\|`ready`\|`failed`)
- `progress` (0–100), `statusMessage`, `urls`, `thumbnailUrl`, `error`

### 6.2 渲染

- Transcript **包含**媒体卡（不再只过滤 user/assistant 文本）。
- **pending/generating**：Shimmer 矩形（按 `ratio`，默认图 1:1、视频 9:16）+ `Generating… {progress}%` + kind 图标（image_outlined / play_circle）。
- **ready**：`Image.network` / 简易视频封面+打开 URL（`url_launcher`）；多 URL 纵向堆叠或 PageView。
- **failed**：错误文案 + 可保留重试提示（P0 不强制重试按钮）。

参考实现：`ai_tools/lib/pages/agent_chat/agent_chat_page.dart` 的 `_buildImageLoadingPlaceholder` / video placeholder（逻辑对齐，不强制拷贝依赖；可用轻量自定义 Shimmer）。

### 6.3 Controller

- 监听 `media.*`，按 `jobId` upsert 卡片。
- `chat.done` / `sending=false` **不清除**未完成媒体卡。
- 保留 `tool.mcp` → `statusLine`（可选）；占位与结果以媒体卡为准。

---

## 7. 错误处理

| 情况 | 行为 |
|---|---|
| MCP 工具抛错 | `media.failed` + tool 错误进 LLM |
| Tracker 超时 | `media.failed`（timeout 文案） |
| 返回无 URL 的 done | `media.failed`（empty result） |
| WS 断开 | Tracker 继续；重连后补发进行中 job 快照（若内存仍有） |
| 非 Creative Expert | 不启用媒体白名单逻辑 |

---

## 8. 测试计划

**后端**

- 单元：结果解析（artifacts / job_id / local id）
- 单元：白名单分类
- 集成 mock：同步工具 → placeholder + ready
- 集成 mock：异步 submit → progress → ready
- 超时 → failed

**Flutter**

- Controller：media 事件 upsert / done 后仍更新
- Widget：generating 显示 %；ready 显示图

**真机冒烟**

1. Creative Expert：「生成一张产品图：…」→ 见占位 → 出图  
2. 异步 submit（若账号可用）→ 占位持续更新 → ready  
3. 断网重连（可选）→ 进行中卡不丢或能恢复  

---

## 9. 实现顺序建议

1. WS 事件类型 + 解析辅助 + MediaJobTracker  
2. agent_loop 接入白名单与 yield/queue  
3. Flutter 模型 / Controller / 占位卡 UI  
4. 真机 Creative 冒烟  

---

## 10. 决策记录

| 决策 | 选择 |
|---|---|
| 视觉参考 | A：ai_tools 聊天 Shimmer + % |
| 范围 | C：Creative 全套媒体工具 |
| 进度通道 | B：后端跟踪 + WS 推送 |
| 架构 | 方案 1：MediaJobTracker |
| 与桌面 | 同一 MCP/schema；Tracker 为手机实时 UX 的基础设施差异 |
