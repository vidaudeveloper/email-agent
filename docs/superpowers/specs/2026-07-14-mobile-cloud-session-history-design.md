# Vidau Mobile Cloud 会话云存储与历史回看 设计

**日期：** 2026-07-14  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（会话列表 · 历史回放 · 继续聊）  
**工作树：** `.worktrees/cloud-agent-p0`

**关联文档：**

- [Cloud Agent 产品设计](./2026-07-11-vidau-cloud-agent-design.md)（§6 `session`：云端会话列表、重连、历史）
- [Mobile Cloud ATTACH](./2026-07-14-mobile-cloud-attach-design.md)（同会话附件；历史回放 P0 以文本为主）
- 桌面会话存储：`desktop-app/website/docs/developer-guide/session-storage.md`（`~/.vidau/state.db`）
- 桌面 UI：`desktop-app/web/src/pages/SessionsPage.tsx`

---

## 1. 目标

参考桌面端本地 SQLite 会话存储，在 **Cloud Agent** 上把已有 `sessions` / `messages` 做成可列表、可回看、可继续聊的云端历史；手机从 Experts 页进入历史并重开会话。

### 1.1 成功标准

1. Experts 页可看到「历史会话」列表（Expert 名、时间、最近一条预览）。
2. 点击某条 → 进入同一 `session_id` 聊天页：HTTP 拉齐历史气泡后，WS 重连，可继续发送。
3. 左滑或长按可删除会话（含消息；附件目录尽力清理）。
4. 权威数据在 Cloud Agent SQLite（对齐桌面 `state.db` 思路）；App 不做本地会话库。
5. 新建会话路径不变：`POST /v1/sessions` → 空聊天。

### 1.2 明确不做（P0）

- 手机本地 SQLite / SharedPreferences 会话权威存储
- 会话标题编辑、全文搜索、父子 lineage / 压缩切分（桌面完整 `vidau_state`）
- 独立「会话」Tab
- 只读预览模式 / 「基于此新建会话」
- 历史气泡内完整还原 ATTACH 媒体（P0 文本回放即可；有 `attachments` 元数据可后补）
- 跨用户 / 多租户强隔离以外的团队共享历史

---

## 2. 已锁定决策

| 议题 | 决策 |
|------|------|
| 范围 | **仅 Cloud 权威**（方案 A） |
| 入口 | Experts 页「历史会话」 |
| 打开行为 | **回放 + 可继续聊**（HTTP 历史 → WS 重连） |
| 列表能力 | Expert / 时间 / preview + **删除**；不做标题 |
| 实现路径 | 扩展现有 Cloud Agent SQLite + REST（方案 1） |
| 工作树 | `.worktrees/cloud-agent-p0` |

---

## 3. 现状与缺口

| 能力 | 桌面 | Cloud Agent 现状 | 缺口 |
|------|------|------------------|------|
| 会话元数据 | `state.db` sessions | SQLite `sessions` | 缺 `updated_at`、列表 API |
| 消息持久化 | messages 表 | `add_message` / `get_session_messages` 已有 | 缺 HTTP 暴露 |
| 历史 UI | Sessions 页 | 无 | Experts 历史区 + 打开回放 |
| 删除 | 有 | 无 | `DELETE` + 级联 |

当前 Flutter `CloudChatController.start()` 只 `connectSession` + 听 WS，**不回填** DB 中已有消息，故返回 Experts 再进同一会话会表现为空聊（除非本进程内存仍在）。

---

## 4. 架构与数据流

```text
ExpertsPage
  │  GET /v1/sessions → 历史列表
  │  DELETE /v1/sessions/{id} → 删除
  │  tap → /cloud-chat/{sessionId}
  ▼
CloudChatController.start()
  │  1) GET /v1/sessions/{id}/messages → 填入气泡
  │  2) WS connect /v1/sessions/{id}/ws
  │  3) 后续 chat.send 仍走现有路径；agent_loop 继续 add_message
  ▼
Cloud Agent SQLite (data/sessions.db)
  sessions(id, expert_id, user_id, status, created_at, updated_at)
  messages(id, session_id, role, content, created_at)
```

权威在服务端；App 仅 UI 缓存列表，下拉刷新以服务端为准。

---

## 5. API 契约

均需 `Authorization: Bearer <token>`。会话须属于当前用户（P0：与现有 `user_id` / token 映射一致；若仍为单机 `default`，保持与 create 相同规则）。

### 5.1 `GET /v1/sessions`

Query（可选）：`expert_id`、`limit`（默认 50，上限 100）、`offset`。

```json
{
  "sessions": [
    {
      "session_id": "uuid",
      "expert_id": "vidau-creative-agent-oneclick",
      "expert_name": "Alex | Creative Designer",
      "status": "ready",
      "created_at": "…",
      "updated_at": "…",
      "message_count": 12,
      "preview": "用这张图生成 9:16…"
    }
  ]
}
```

排序：`updated_at DESC`（无消息时用 `created_at`）。

`preview`：最近一条 `role in (user, assistant)` 的 `content` 截断（建议 ≤ 80 字）；空会话可为 `""` 或省略。

### 5.2 `GET /v1/sessions/{session_id}/messages`

```json
{
  "session_id": "uuid",
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "…",
      "created_at": "…"
    }
  ]
}
```

404：会话不存在。P0 不分页；若消息极多可后续加 `before_id` / `limit`。

### 5.3 `DELETE /v1/sessions/{session_id}`

```json
{ "ok": true }
```

删除顺序：messages → session 行 → 尽力删除 `data/sessions/{session_id}/` 附件目录。404 若不存在。

### 5.4 既有 API（不变）

- `POST /v1/sessions` — 新建  
- WS `chat.send` / 事件流 — 继续聊；`add_message` 时刷新 `sessions.updated_at`

---

## 6. Schema 变更

```sql
-- sessions：新增 updated_at（迁移：已有行用 created_at 回填）
ALTER TABLE sessions ADD COLUMN updated_at TEXT;
-- 应用层：CREATE 时 updated_at = created_at；add_message 时 UPDATE updated_at
```

SQLite 无列则 `ALTER`；`init_db` 做幂等迁移。不引入桌面 FTS / title / parent_session_id。

---

## 7. 移动端 UX

### 7.1 Experts 页

- 专家列表上方或下方增加 **「历史会话」** 区块（或「查看历史」进入二级列表页，二选一实现，推荐二级页避免 Experts 过长）。
- 列表行：Expert 名、相对/绝对时间、`preview` 一行。
- 左滑删除（iOS 风格）或长按 → 确认对话框 → `DELETE`。
- 下拉刷新。
- 空态：「还没有会话，从上方专家开始聊天」。

### 7.2 打开历史

- `go_router` 仍用 `/cloud-chat/:sessionId`，extra 带 `expertName`（列表项已有则传入）。
- `start()`：
  1. `GET .../messages` → 映射为 `CloudDisplayMessage`（user/assistant；跳过或折叠非聊天气泡 role 若有）
  2. `connectSession`
  3. 滚动到底
- 若 GET 404：SnackBar「会话不存在」并返回 Experts。

### 7.3 新建 vs 历史

- 点 Expert → 仍 **新建** `POST /v1/sessions`（与今日一致）。
- 历史入口只负责重开，不替代新建。

---

## 8. 错误与边界

| 场景 | 行为 |
|------|------|
| 列表失败 | 展示错误 + 重试 |
| 消息拉取失败 | 不进空聊假装成功；提示并返回 |
| 删除失败 | SnackBar；列表不乐观删或回滚 |
| 正在该会话聊天时删除 | P0：从历史删后若仍停留聊天页，下次发送可 `chat.error`；可选监听后 pop |
| WS 已连时再次打开同会话 | dispose 旧 controller / 单例连接策略与现网一致 |
| `add_message` 仅存文本 | 历史无附件缩略图属已知限制 |

---

## 9. 文件地图（实现时）

| 文件 | 职责 |
|------|------|
| `backend/app/sessions.py` | `list_sessions` / `delete_session` / `updated_at` 迁移 |
| `backend/app/main.py` | 三个 HTTP 路由 |
| `backend/tests/test_session_history.py` | 列表、消息、删除、权限/404 |
| `lib/cloud/cloud_api_client.dart` / `cloud_client.dart` | list / messages / delete |
| `lib/cloud/models/cloud_models.dart` | `CloudSessionSummary` 等 |
| `lib/state/cloud_chat_controller.dart` | start 时拉历史 |
| `lib/features/experts/…` 或新 `session_history_page.dart` | 列表 UI |

---

## 10. 验收清单

1. 新建会话聊几轮 → Experts 历史出现，preview 为最近内容。  
2. 杀掉 App 或返回 Experts 再点该会话 → 气泡齐全且可继续问。  
3. 删除后列表消失；再 GET messages → 404。  
4. 无会话时有空态。  
5. 后端 pytest 覆盖 list / messages / delete。  

---

## 11. 与桌面的对齐说明

| 桌面 | Cloud P0 |
|------|----------|
| `~/.vidau/state.db` | `backend/data/sessions.db` |
| Sessions 页 | Experts → 历史会话 |
| 打开继续聊 | 同 |
| title / FTS / lineage | 不做 |
| source 多端标签 | 可不做；可选固定 `source=mobile-cloud` 预留列（P0 可不加列） |

---

## 12. 分期

| 阶段 | 内容 |
|------|------|
| **P0（本文）** | list / messages / delete + Experts 历史 + 打开回放继续聊 |
| **P1** | 标题、按 Expert 筛选、消息分页、历史附件预览 |
| **P2** | 搜索、归档、与桌面 transcript 互通（若产品需要） |
