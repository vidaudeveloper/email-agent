# Vidau Mobile Link 一期设计文档

**日期：** 2026-07-10  
**状态：** 待审阅  
**产品：** Vidau Mobile（对标 WorkBuddy「链接电脑」）  
**范围：** 一期 — 账号云中转连通 + 真实执行 + 双端同步会话；双端各自本地存储

---

## 1. 目标

### 1.1 产品目标

让用户在手机上用聊天方式驱动桌面 Vidau Agent 真实执行任务，并在手机与桌面会话中同步看到指令与执行结果（类似 WorkBuddy 链接电脑）。

### 1.2 一期成功标准

1. 手机与电脑登录同一 Vidau / Nous Portal 账号。
2. 手机能发现在线电脑并选中。
3. 手机发送指令 → 桌面写入现有 Agent 会话并真实执行。
4. 执行流（progress / assistant / done）同步回手机；桌面 TUI/CLI 同会话可见。
5. 历史各自落本地；云 Gateway 不存聊天正文。

### 1.3 一期明确不做

- 云端聊天历史 / 云端会话库
- 局域网扫码直连（可作为后续增强）
- 桌面端新建 GUI 聊天窗
- 多电脑并行控制、语音、推送、Skill 市场切换协议

---

## 2. 已锁定决策

| 议题 | 决策 |
|---|---|
| 连接方式 | 账号云中转（Account Gateway），非局域网扫码 |
| 能力深度 | 连通 + 真实执行 + 双端同步（非仅 ping） |
| 移动端技术栈 | Flutter（iOS + Android） |
| 鉴权 | 复用 Vidau / Nous Portal SSO + JWT |
| 桌面展示 | 写入现有 TUI/CLI 会话；不新做桌面聊天 GUI |
| 架构 | Mobile 作为桌面 Gateway 的新 channel |
| 持久化 | 双端各自本地存储；Gateway 只转发 |

---

## 3. 桌面端会话存储调研

桌面端 Vidau **已经在本机持久化会话**（不依赖云端会话库）：

| 层级 | 位置 | 内容 |
|---|---|---|
| 会话索引 | `$VIDAU_HOME/sessions/sessions.json` | `session_key → session_id` 与元数据 |
| 权威 transcript | `$VIDAU_HOME/state.db`（`SessionDB` / SQLite） | 会话元数据 + 消息正文；支持 FTS5 搜索 |
| 降级路径 | `{session_id}.jsonl` | 仅在 SQLite 不可用时使用 |
| 运行时 API | `gateway.session.SessionStore` | 内存 `_entries` + 落盘 |

Telegram 等消息通道已通过 `SessionStore` 写入本地 SQLite。一期「双端各自本地存储」与现有架构一致；云 Gateway 只做中转。

参考：`desktop-app/docs/session-lifecycle.md`、`gateway/session.py`、`vidau_state.py`。

---

## 4. 产品设计

### 4.1 主用户路径

```
登录（SSO）
  → 设备列表（在线 / 离线）
  → 选择电脑
  → 聊天：发送文本指令
  → 桌面会话出现同一条用户消息并执行
  → 手机流式展示结果 + 桌面 TUI/CLI 同步可见
  → 断线后，各端本地仍可回看近期历史
```

### 4.2 存储策略

| 端 | 存什么 | 怎么存 |
|---|---|---|
| 桌面 | 权威会话与执行 transcript | 复用 `state.db` + `sessions.json`；mobile 作为新 channel |
| 手机 | 设备、消息、连接状态的 UI 缓存 | Flutter 本地库（`drift` 或 `sqflite`） |
| 云 Gateway | 设备在线映射与连接元数据 | Redis：`user_id:device_id → socket/status`；**不持久化消息正文** |

同步模型：

- **实时同步：** 经 Gateway 的 WebSocket 事件（`chat.*`）
- **持久化：** 各端写各端；桌面是执行侧 transcript 的权威源
- **重连补齐：** 手机可通过设备通道向桌面 `history.pull` 最近 N 条（仍不落云）

### 4.3 体验要点

- 登录后一期首页为设备列表。
- 聊天页头部展示已连接电脑名称与在线状态。
- 桌面等待工具审批时，手机显示「等待电脑确认」。
- 设备离线时禁用发送，或给出明确的重连指引。

---

## 5. 技术架构

### 5.1 拓扑

```text
Flutter 手机 ──HTTPS/WSS──► Cloud Link Gateway ◄──HTTPS/WSS── 桌面 Vidau
                                      │                         │
                                      ▼                         ▼
                              Redis 设备在线表            state.db + sessions.json
                              （不存聊天正文）            （权威 transcript）
                                      │
                                      ▼
                              手机本地 SQLite
                              （仅缓存）
```

### 5.2 组件职责

| 组件 | 一期职责 |
|---|---|
| Cloud Link Gateway | JWT 鉴权、设备注册/心跳、按 `user_id` 转发消息 |
| 桌面 `mobile` channel | 连接 Gateway、接收指令、注入现有 Agent 管线、回推流式事件 |
| Flutter App | 登录、设备列表、聊天 UI、流式渲染、本地缓存 |
| 现有 `SessionStore` | 权威会话与 transcript |

桌面适配器优先通过现有 `platform_registry` 以插件方式注册（与其他非核心平台同模式）。仅在枚举/配置路径确有需要时再增加 `Platform.MOBILE`。

### 5.3 会话路由

- 每台桌面安装生成稳定 `device_id`（安装 ID / 机器指纹）。
- 手机选中某台电脑后，会话 lane 为：

```text
agent:main:mobile:dm:{device_id}:{mobile_user_id}
```

- 入站手机消息使用 `SessionSource(platform=mobile, ...)`，进入与其他 channel 相同的 `_handle_message` / Agent 路径。
- 一期桌面「可见」验收标准：消息进入该会话 transcript，并在 TUI/CLI 查看该会话时可看到。不要求强制抢占当前交互焦点（可作为可选项）。

### 5.4 协议

#### REST

| 接口 | 用途 |
|---|---|
| `POST /auth/*` | 复用 Portal/SSO；签发/刷新 JWT |
| `GET /devices` | 当前用户下桌面设备列表 + 在线状态 |
| `POST /devices/rename`（可选） | 修改显示名 |

#### WebSocket 消息类型

| type | 方向 | 用途 |
|---|---|---|
| `register_device` | 桌面 → Gateway | 注册设备；标记 online |
| `ping` / `pong` | 双向 | 心跳（约 20s） |
| `device_status` | Gateway → 手机 | 上下线推送 |
| `chat.send` | 手机 → Gateway → 桌面 | 用户指令文本 |
| `chat.user` | 桌面 → Gateway → 手机 | 已入会话的用户消息回显（稳定 id） |
| `chat.assistant` | 桌面 → Gateway → 手机 | 助手分段/最终回复 |
| `chat.progress` | 桌面 → Gateway → 手机 | 工具/日志进度（可节流） |
| `chat.done` / `chat.error` | 桌面 → Gateway → 手机 | 本轮结束或失败 |
| `history.pull` / `history.snapshot` | 手机 ↔ 桌面（经 Gateway） | 重连后回填最近 N 条 |

公共字段：`msg_id`、`session_id`、`device_id`、`user_id`、`ts`。JWT 握手后由连接态携带鉴权上下文。

一期 **不包含** skill 切换协议、文件传输、语音、多设备并行控制。

### 5.5 时序

```text
桌面：register_device + JWT
手机：login + GET /devices → 设备 online
手机：chat.send(text, device_id)
Gateway：转发到桌面 socket
桌面：SessionSource(mobile) → handle_message → Agent
桌面：发出 chat.user / chat.progress / chat.assistant / chat.done
Gateway：fan-out 到同一 user_id 的在线手机
桌面：append transcript → state.db
手机：缓存事件 → 本地 SQLite
```

### 5.6 桌面 mobile channel 接入要点

1. gateway/桌面启动后，若已 Portal 登录且开启 mobile link → 连接 Cloud Gateway 并 `register_device`。
2. 收到 `chat.send` → 构造 `SessionSource` → 走现有入站路径。
3. 将 `stream_consumer` / delivery 钩子映射为 `chat.*` WS 事件经 Gateway 回传。
4. 仅接受 Gateway 已鉴权、且 `user_id` 与本机登录账号一致的消息。
5. 桌面断线 → Gateway 标记 offline → 手机设备列表变灰。

### 5.7 安全（一期最小集）

- 全程 HTTPS / WSS + JWT
- 仅在同一 `user_id` 的设备间转发
- `msg_id` + `ts` 做基础重放防护
- Gateway 不持久化聊天正文（必要时仅短时内存队列）
- 高危工具审批：复用桌面现有 approval；手机显示等待确认状态

---

## 6. 仓库与模块拆分

### 6.1 仓库边界

| 仓库 | 一期工作 |
|---|---|
| `mobile_agent`（本仓库） | Flutter App |
| `desktop-app` | `mobile` platform/channel 适配器 |
| `link-gateway`（新建服务或放入现有后端仓） | Auth 校验、`/devices`、WSS 转发、Redis 注册表 |

### 6.2 Flutter 模块

| 模块 | 职责 |
|---|---|
| `auth` | Portal/SSO、JWT 刷新、安全存储 |
| `devices` | 设备列表、在线状态、选择目标电脑 |
| `link` | WSS 连接/重连/心跳/编解码 |
| `chat` | 聊天 UI、发送、流式渲染 |
| `local_db` | 设备/消息/会话缓存 |
| `app_shell` | 路由：登录 → 设备 → 聊天 |

### 6.3 桌面模块

| 模块 | 职责 |
|---|---|
| `platforms/mobile` 或 plugin | 适配器：连 Gateway + `register_device` |
| inbound bridge | `chat.send` → 现有 `_handle_message` |
| outbound bridge | stream/delivery → `chat.*` |
| config | 功能开关、Gateway URL、持久化 `device_id` |

### 6.4 Gateway 模块

| 模块 | 职责 |
|---|---|
| Auth middleware | 校验 JWT；绑定 `user_id` |
| Device registry | Redis 在线表 |
| Relay | 按 `target_device` / `user_id` 转发 |
| REST | `GET /devices`、健康检查 |

---

## 7. 验收清单

### 连通

- [ ] 同账号登录后，手机能在 5 秒内看到电脑 online
- [ ] 电脑退出/离线后，手机设备状态正确更新
- [ ] 心跳与自动重连在网络闪断后可用

### 真实执行 + 同步

- [ ] 手机指令触发桌面 Agent **真实执行**
- [ ] 同一条用户消息写入桌面 `state.db` transcript，并在 TUI/CLI 会话中可见
- [ ] progress 与最终结果实时出现在手机
- [ ] 一轮结束后，双端本地均可回看该轮消息

### 存储与安全

- [ ] Gateway 不持久化聊天正文
- [ ] 异账号无法看到或控制对方设备
- [ ] 清除 App 数据后手机历史可丢失（符合一期定义）

---

## 8. 建议排期（约 4–5 周）

| 周 | 交付 |
|---|---|
| W1 | Gateway 骨架：JWT、注册、心跳、echo 转发；桌面可 `register_device` |
| W2 | 桌面 `mobile` channel 接入 `_handle_message`；Flutter 登录 + 设备列表 + 基础 WSS |
| W3 | 聊天闭环：`chat.send` → 真实执行 → progress/assistant/done 回手机；桌面 transcript 落库 |
| W4 | 手机本地缓存、重连 `history.pull`、离线 UX、鉴权与错误态 |
| W5 | 内测打磨：节流、approval 等待态、稳定性与文档 |

---

## 9. 风险与应对

| 风险 | 应对 |
|---|---|
| 移动端 Portal SSO 对接慢 | 优先复用现有 OAuth / device-code；系统浏览器或 WebView 回调 |
| progress 事件过多卡 UI | 节流/合并 `chat.progress`；保证最终 `assistant`/`done` 必达 |
| TUI 当前焦点不是 mobile 会话 | 一期以 transcript 可见为准；可选「有手机消息到达」提示 |
| Gateway 技术栈争议 | 用团队最熟栈（FastAPI 或 Go）；上文协议冻结为契约 |

---

## 10. 二期预览（当前不做）

- 云端会话同步 / 多端历史
- 同网时的局域网扫码快路径
- 桌面 GUI「链接手机」面板
- 电脑上线或任务完成时的推送通知
- P2P/WebRTC 优化，失败回退 Gateway

---

## 11. 参考资料

- `/Users/kean/docs/Vidau-Mobile-Link-Account-Gateway.md` — 账号云中转方案
- `/Users/kean/docs/Vidau-Mobile-Link-Product-Phase1.md` — 早期局域网产品稿（连接模型已被本文替代）
- `desktop-app/docs/session-lifecycle.md` — 本地会话存储
- `desktop-app/gateway/session.py` — `SessionStore`
- `desktop-app/gateway/platform_registry.py` — 平台适配器注册
