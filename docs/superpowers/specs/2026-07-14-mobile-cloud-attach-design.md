# Vidau Mobile Cloud Composer ATTACH 设计

**日期：** 2026-07-14  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（聊天输入附件）  
**工作树：** `.worktrees/cloud-agent-p0`

**关联文档：**

- [Cloud Agent 产品设计](./2026-07-11-vidau-cloud-agent-design.md)
- [Cloud Agent 媒体生成进度](./2026-07-11-cloud-agent-media-progress-design.md)（输出媒体；本文为**输入**附件）
- 桌面 ATTACH：`desktop-app/apps/desktop/src/app/chat/composer/context-menu.tsx`
- Creative 上传 skill：`creative-platform`（`creative_get_upload_instructions` / `creative_upload_reference`）
- 交互草图：Cursor canvas `mobile-attach-composer.canvas.tsx`

---

## 1. 目标

对齐桌面 Composer 红框 **ATTACH**，在 **Cloud 聊天** 中支持用户从手机添加参考素材，并在发送后供 Agent（尤其 Creative）使用。

### 1.1 成功标准

1. Cloud 聊天输入栏 `+` → 底部 Sheet：相册图片、相册视频、URL。
2. 选中后上传到 Cloud Agent，输入框上方显示 chip；可删除。
3. 发送时 `chat.send` 携带正文 + `attachment_ids`；**用户气泡内嵌缩略图/视频封面**（对齐桌面消息内预览，而非仅显示 `@ref` 文本）。
4. `@` 仅补全**本会话已上传**的图片 / 视频 / URL；无附件时不弹列表；补全项带缩略图。
5. Creative Expert 需要参考图时，由 **Cloud Agent 服务端**桥接为 HTTPS URL（不经 App 持有 MCP Key）。
6. 非 Creative Expert：附件仍进入会话上下文，不强制 Creative 桥接。
7. 助手追问比例等可选项时，手机展示**可点 Chip**（一点即可回复），降低打字成本。

### 1.2 明确不做（一期）

- Link（连电脑）模式 ATTACH
- Files… / Folder… / Paste image / Prompt snippets（可 P1）
- `@` 沙箱路径或桌面 `complete.path`
- App 直连 `creative.vidau.ai` MCP
- 社区任意文件类型上传治理

---

## 2. 已锁定决策

| 议题 | 决策 |
|------|------|
| 产品线 | **仅 Cloud**（`cloud-chat`） |
| ATTACH 项 | 相册图片、相册视频、URL |
| `@` | 仅本会话已上传的 image / video / url |
| 传输架构 | **HTTP 先上传拿 ref，再 WS 发送**（对齐桌面 attach 模型） |
| Creative | 服务端桥接：`get_upload_instructions`（优先）或小文件 `upload_reference` |
| Key 边界 | API Key / MCP Key 只在 Cloud Agent；Flutter 只持 session token |

---

## 3. 架构与数据流

```text
Flutter Cloud Chat
  │  + Sheet → 相册图/视频 | URL
  │  POST /v1/sessions/{id}/attachments
  ▼
Cloud Agent
  ├─ 存会话附件 → attachment_id + ref
  ├─ GET  /v1/sessions/{id}/attachments   （@ 补全源）
  ├─ DELETE /v1/sessions/{id}/attachments/{id}
  └─ WS chat.send { content, attachment_ids[] }
        │
        ▼
   Agent loop
        ├─ 通用：ref + URL 注入用户消息上下文
        └─ Creative Expert：桥接
              creative_get_upload_instructions → 服务端 PUT
              或 creative_upload_reference(content_base64)
              → file_url → reference_urls / reference_image_urls
```

### 3.1 附件模型

| 字段 | 说明 |
|------|------|
| `id` | 会话内唯一，如 `att_01` |
| `kind` | `image` \| `video` \| `url` |
| `label` | 展示名 |
| `ref` | `@image:att_01` / `@video:…` / `@url:…` |
| `url` | 可访问 HTTPS（url 类直接存；上传类为内部或桥接后 URL） |
| `preview_url` | 可选缩略图 |
| `mime` / `size` | 校验与 UI |
| `created_at` | 排序 |

---

## 4. Flutter UI

### 4.1 入口与 Sheet

- 输入栏左侧 `+` 打开底部 Sheet（非桌面浮层菜单）。
- 一期三项：

| 项 | 行为 |
|----|------|
| 相册图片 | 系统相册多选 → 立即 `POST .../attachments` → chip |
| 相册视频 | 相册选视频（一期单选优先）→ 同上 |
| 链接 URL… | 模态输入框，校验 `http(s)://` → `kind=url` → chip |

### 4.2 Chip 区

- 位于输入框上方：缩略图 / 文件名 / `@url:…`
- 上传中转圈；失败可重试或删除
- × → `DELETE`（或未成功上传仅清本地）

### 4.3 发送

- `content`：用户正文（可含已插入 `@ref`）
- `attachment_ids`：本条挂上的 id
- 允许无正文仅附件
- **发送成功后**：composer chip 清空；附件预览进入用户气泡（见 4.6）

### 4.4 `@` 补全

- 有会话附件时，输入 `@` 弹出列表（图 / 视频 / URL）
- 列表项带缩略图 / 类型标（不只纯文字 ref）
- 选中插入对应 `ref` 文本
- 无附件：不弹层，轻提示「先添加图片、视频或链接」

### 4.5 权限与限制（UI）

- 相册权限拒绝 → 明确文案
- 图片建议 ≤ 25MB（对齐 Creative 参考图）
- 单轮参考图建议上限 9（对齐 `reference_image_urls`）
- 视频超限提示换小文件（一期建议 ≤ 100MB，可配置）

### 4.6 用户气泡内嵌预览（对齐桌面消息样式）

桌面在用户气泡中直接展示参考图缩略图；手机一期必须对齐该**结果态**，避免只显示 `@image:att_xx`。

| `kind` | 气泡表现 |
|--------|----------|
| `image` | 圆角缩略图（可点全屏 / 原图） |
| `video` | 封面 + 时长角标；可点用系统播放器 / 内嵌播放 |
| `url` | 单行卡片：域名 + 截断 URL，可点外开 |

布局建议：

- 文案在上、媒体在下（或多图横向滑动，上限与发送一致）
- 数据来自入站 `chat.user` 的 `attachments[]`（含 `preview_url` / `url` / `kind` / `label`）
- 乐观发送：本地先用上传响应里的 `preview_url` 渲染，待 WS 回放可对齐

### 4.7 助手追问 Chip（手机优化）

桌面靠用户打字回答「9:16 / 1:1 / 16:9」等；手机增加可点选项，降低摩擦。

| 来源 | 一期策略 |
|------|----------|
| 结构化事件（推荐，可后置） | 若后续增加 `chat.choices` / `ask.user` 则渲染 Chip |
| P0 务实做法 | 助手文案中识别常见比例选项时，由客户端启发式抽出 Chip；或 Creative 流程固定展示「9:16 / 1:1 / 16:9」快捷条（仅 Creative 会话） |

Chip 点击：把选项文本作为一条用户消息发送（或填入输入框并聚焦，二选一；**默认直接发送**更接近桌面确认节奏）。

**不做：** 把桌面侧栏、Credits、模型条、Gateway 状态条搬进聊天首屏。

---

## 5. HTTP / WS 协议

### 5.1 HTTP

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/sessions/{session_id}/attachments` | multipart `file`，或 JSON `{ "kind":"url", "url":"https://..." }` |
| `GET` | `/v1/sessions/{session_id}/attachments` | 列表（chip / `@`） |
| `DELETE` | `/v1/sessions/{session_id}/attachments/{id}` | 删除 |

鉴权：`Authorization: Bearer <session_token>`（与现有 Cloud 一致）。

**POST 成功响应：**

```json
{
  "id": "att_01",
  "kind": "image",
  "label": "花海.jpg",
  "ref": "@image:att_01",
  "mime": "image/jpeg",
  "size": 123456,
  "preview_url": "https://…/preview",
  "url": "https://…/object"
}
```

### 5.2 WebSocket `chat.send`（扩展）

```json
{
  "type": "chat.send",
  "session_id": "…",
  "content": "根据图片生成\n@image:att_01",
  "attachment_ids": ["att_01", "att_02"]
}
```

- `attachment_ids` 必须属于该会话且已上传成功
- 服务端注入本轮用户消息上下文
- 入站 `chat.user` **必须**带回可渲染附件，供气泡内嵌预览：

```json
{
  "type": "chat.user",
  "content": "根据图片进行优化，生产写实的图片",
  "attachments": [
    {
      "id": "att_01",
      "kind": "image",
      "label": "ref.jpg",
      "ref": "@image:att_01",
      "preview_url": "https://…/preview",
      "url": "https://…/object"
    }
  ]
}
```

向后兼容：缺省 `attachment_ids` / `attachments` 时行为与现网纯文本一致。

### 5.3 Creative 桥接

仅当会话 Expert 需要参考素材且目标工具接受 `reference_urls` / `reference_image_urls` 时：

1. 收集本轮 image/video（及可用的 https url）附件  
2. 若 Cloud Agent 已有 Creative 可访问的 HTTPS `url` → 直接使用  
3. 否则优先 `creative_get_upload_instructions` → **服务端 PUT** → `upload.file_url`  
4. 小文件兜底：`creative_upload_reference`（`content_base64`）  
5. 桥接失败：可读错误事件/助手文案，不静默丢参考图  

官方约束（creative-platform skill）：生成工具只要 HTTPS URL；勿对 remote MCP 传 `local_path`；勿默认大 base64。

---

## 6. 存储

| 位置 | 内容 |
|------|------|
| `data/sessions/{session_id}/attachments/` | 图/视频二进制（P0 本地盘） |
| `data/sessions/{session_id}/attachments.json` | 元数据 |
| 内存索引 | 按 session 校验 `attachment_ids` |

- URL 附件只写元数据  
- 会话销毁或 TTL 时清理  
- P0 可不接通用对象存储；Creative 桥接时再 PUT 到其预签名地址  

---

## 7. 错误态

| 场景 | 表现 |
|------|------|
| 相册权限拒绝 | SnackBar / Sheet 内说明 |
| 超大小 / 超数量 | 上传前拦截 |
| 上传失败 / 超时 | chip 错误 + 重试；不得进入 `attachment_ids` |
| URL 非法 | 输入框内联错误 |
| 非法 `attachment_ids` | `chat.error` |
| Creative 桥接失败 | 可读错误；不假成功 |
| 无附件时 `@` | 不弹列表 + 轻提示 |

---

## 8. 实现草图（文件）

**Backend（`cloud-agent-p0`）：**

- `cloud_agent/app/attachments.py` — 存储与 CRUD  
- `cloud_agent/app/main.py` — attachments 路由  
- `cloud_agent/app/ws.py` — `chat.send` 解析 `attachment_ids`  
- `cloud_agent/app/agent_loop.py`（或邻接模块）— Creative 桥接  
- tests：`test_attachments.py`

**Flutter：**

- `lib/features/chat/cloud_chat_page.dart` — `+` / Sheet / chip / `@`  
- `lib/state/cloud_chat_controller.dart` — 上传与发送  
- `lib/cloud/cloud_api_client.dart` — attachments API  
- 依赖：`image_picker`（及必要权限配置）

---

## 9. 验收清单

1. 选相册图 → chip → 发送 → **用户气泡内嵌缩略图**（非仅 `@ref` 文本）；Creative + Key 下可作参考图生成  
2. 视频、URL 同上（封面 / 链接卡）；`GET attachments` 与 `@` 一致；`@` 列表带缩略图  
3. 删除附件后 chip 与 `@` 同步消失；发送后 composer chip 清空  
4. Creative 会话可点比例 Chip 完成追问（或等价快捷条）  
5. 非 Creative Expert：可上传并进上下文，不强制桥接  
6. Flutter 无 MCP/OpenVidAU API Key 泄露；聊天首屏无桌面侧栏级密度  

---

## 10. 后续（非本期）

- Paste image、Prompt snippets  
- Link 模式附件（需桌面 gateway 协议）  
- Files / Folder、`@` 沙箱路径  
- 统一对象存储与跨会话素材库  
