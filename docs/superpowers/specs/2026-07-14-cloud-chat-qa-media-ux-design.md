# Cloud Chat 问答 + 媒体加载 UX 设计

**日期：** 2026-07-14  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（聊天会话界面）  
**工作树：** `.worktrees/cloud-agent-p0`（`feature/cloud-agent-p0`）

**关联文档：**

- [Cloud Agent 产品设计](./2026-07-11-vidau-cloud-agent-design.md)
- [媒体生成实时进度](./2026-07-11-cloud-agent-media-progress-design.md) — `media.*` 协议与 Tracker（本文为其 **UX 叠加**，不替换协议）
- [Composer ATTACH](./2026-07-14-mobile-cloud-attach-design.md) — 输入附件（与本文正交）

**参考：** Manus 对话方案（纯问答主路径、媒体生成加载态、底部悬浮阶段条）；不照搬多步骤任务卡 / 知识建议卡 / 硬确认门控。

---

## 1. 目标

优化 Cloud 会话界面为 **问答模式**，并在返回图片 / 视频时提供 Manus 风格的加载反馈。

### 1.1 成功标准

1. 主列表只呈现问答相关内容：用户气泡、助手文本、流内 Phase 卡、媒体卡。
2. 生成图片 / 视频时：立刻出现 Shimmer 占位 + 进度；完成后原地换成可预览媒体。
3. 输入框上方有悬浮阶段条；用户滚动聊天时仍能看到「还在做」。
4. 流内 Phase 卡与悬浮条共用同一份客户端状态，完成后有明确收起规则，避免信息重复烦人。
5. **不改后端协议**；复用已有 `media.placeholder|progress|ready|failed`。

### 1.2 已锁定决策

| 议题 | 决策 |
|------|------|
| 范围能力 | **A + B + C**：纯问答展示 + 媒体 Shimmer + 悬浮阶段条 |
| 落地方式 | **方案 2**：流内 Phase 卡 + 底部悬浮条双位置 |
| 协议 | 零后端变更；Flutter 消费现有 `media.*` / `chat.progress` / `tool.mcp` |
| 产品线 | **仅 Cloud Chat**（本期不改 Link） |

### 1.3 明确不做（本期）

- 多步骤「任务进度 4/5」可折叠步骤列表（Manus D）
- 确认后服务端硬门控执行（Manus E）
- 助手 token / delta 流式输出
- 会话历史完整回放媒体卡（可 P1；当前连接生命周期优先）
- Link 模式同步改造
- 新增 WS 字段 `phase_label`（可用现有 `message` + 本地 tool 名映射）

---

## 2. 对话结构（纯问答）

### 2.1 主列表保留

| 项 | 说明 |
|----|------|
| 用户气泡 | 含附件预览（ATTACH 已有能力） |
| 助手文本 | `chat.assistant` |
| 流内 Phase 卡 | 进行中完整展示；就绪/失败后折叠为一行摘要 |
| 媒体卡 | Shimmer → 图 / 视频 / 错误态（按 `job_id`） |

### 2.2 不进主列表

| 事件 | 去向 |
|------|------|
| `chat.progress` | 仅驱动悬浮条（无活跃 media job 时） |
| `tool.mcp` | 同上 |
| `sandbox.status` | 不进主列表；本期不驱动悬浮条（避免噪音） |

---

## 3. 共享状态与双位置同步

### 3.1 `PhaseUiState`（客户端）

每个活跃 `job_id`（及无媒体时的「回合思考」）维护：

| 字段 | 说明 |
|------|------|
| `jobId` | 媒体 job；无媒体时可为 `turn-{msgId}` |
| `kind` | `image` \| `video` \| `audio` \| `other` \| `thinking` |
| `label` | 优先 `media.progress.message`，否则 tool 名友好映射 |
| `progress` | 0–100 |
| `elapsed` | 客户端本地计时（`placeholder` 起算） |
| `thumbnailUrl` | 可选 |
| `status` | `active` \| `ready` \| `failed` |

流内 Phase 卡与底部悬浮条 **都读这份状态**，不各自解析事件。

### 3.2 进行中

- 流内 Phase：缩略图 + 标题（如「生成中 · 视频」）+ label + 进度% + elapsed
- 悬浮条：同文案摘要；滚动时仍可见
- 媒体 Shimmer：同 `progress` / `ratio`
- 点击悬浮条 → 滚动到对应流内卡 / 媒体卡

### 3.3 就绪 / 失败

| 结果 | 媒体卡 | 流内 Phase | 悬浮条 |
|------|--------|------------|--------|
| `media.ready` | 展示图/视频 | 折叠为一行「已完成 · {kind}」 | ~1.2s 后淡出 |
| `media.failed` | 错误文案 | 折叠为「生成失败」 | 可手动关闭；或保留至下一条用户消息 |

### 3.4 事件 → UI

| 事件 | 行为 |
|------|------|
| `media.placeholder` | 插入流内 Phase + 媒体 Shimmer；显示悬浮条；开始 elapsed |
| `media.progress` | 更新共享状态（两处 + Shimmer %） |
| `media.ready` | 媒体出结果；Phase 折叠；悬浮条淡出 |
| `media.failed` | 媒体错误；Phase 折叠失败；悬浮条可关 |
| `chat.progress` / `tool.mcp` | **无活跃 media job** 时仅更新悬浮条；**有 media 时不覆盖** media 文案 |
| `chat.done` | 不清除未完成媒体卡；Tracker 仍可推送 `media.*` |

### 3.5 多 job

- 流内：每个 `job_id` 一张 Phase + 一张媒体卡
- 悬浮条：只显示 **最近更新** 的 job；若还有其他进行中，右侧显示「+N」

---

## 4. 媒体卡视觉

对齐已有媒体进度设计与 Manus 加载意图：

- **pending / generating：** Shimmer 矩形（按 `ratio`；默认图 1:1、视频 9:16）+ `Generating… {progress}%` + kind 图标
- **ready：** `Image.network` / 视频封面 + 打开 URL
- **failed：** 可读错误文案

不引入 Creation 页 GIF；不在手机端 HTTP 轮询 job。

---

## 5. 架构与数据流

```text
Cloud Agent (已有)
  media.placeholder | progress | ready | failed
  chat.progress | tool.mcp | chat.assistant | chat.done
        │
        ▼
Flutter CloudChatController
  ├─ 解析 media.* → upsert MediaCard + PhaseUiState
  ├─ progress/tool → 仅更新悬浮条（无 media 时）
  └─ transcript 过滤：不插入 progress/tool/sandbox 气泡
        │
        ▼
CloudChatPage
  ├─ 列表：user / assistant / PhaseCard / MediaCard
  └─ 叠层：PhaseFloatingBar（读同一 PhaseUiState）
```

---

## 6. 实现草图（文件）

均在 Cloud worktree Flutter 侧：

| 文件 | 变更 |
|------|------|
| `lib/cloud/models/cloud_models.dart` | `CloudEventType` 增加 media.*；payload 字段 |
| `lib/state/cloud_chat_controller.dart` | 消费 media.*；`PhaseUiState`；transcript 过滤 |
| `lib/features/chat/cloud_chat_page.dart` | Phase 卡、媒体卡、悬浮条布局 |
| 可选 | `phase_status_card.dart` / `media_job_card.dart` / `phase_floating_bar.dart` |

**后端：** 无变更（`media_tracker` / `agent_loop` / `media_hub` 已具备）。

---

## 7. 错误与边界

| 场景 | 行为 |
|------|------|
| WS 在 `chat.done` 后仍收 `media.*` | 正常更新对应 `job_id` |
| 未知 `job_id` 的 progress | 忽略或建孤儿卡（优先忽略） |
| 非 Creative / 无媒体工具 | 无 Shimmer；最多短暂「思考中」悬浮条 |
| 重连 | P0：内存中进行中 job 若后端补发快照则恢复；否则丢失可接受（与媒体进度设计一致） |

---

## 8. 验收清单

1. Creative：「生成一张图」→ 流内 Phase + Shimmer + 悬浮条 → 出图 → Phase 折叠、条消失。
2. 生成中向上滚动 → 悬浮条仍可见；点击回到媒体卡。
3. 非媒体问答：主列表无工具噪音；无 Shimmer。
4. 主列表无 `tool.mcp` / 原始 `chat.progress` 气泡。
5. 异步长任务：`chat.done` 后进度仍更新直至 ready/failed。

---

## 9. 测试计划

- Controller：media 事件 upsert；done 后仍更新；progress 不进 messages 列表。
- Widget：generating 显示 %；ready 显示图；悬浮条与流内状态一致。
- 真机冒烟：验收清单 1–5。

---

## 10. 决策记录

| 决策 | 选择 |
|------|------|
| Manus 能力子集 | A + B + C |
| 双位置 vs 仅悬浮条 | 方案 2（流内 + 悬浮） |
| 协议 | 不新增字段；复用 media.* |
| 计时 | 客户端 elapsed |
| 范围 | Cloud only；Flutter only |
