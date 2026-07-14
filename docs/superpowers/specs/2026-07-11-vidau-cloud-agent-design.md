# Vidau Cloud Agent 产品设计文档

**日期：** 2026-07-11（修订：2026-07-14）  
**状态：** P0 实施中（本地 Dev Profile 已交付主路径）  
**产品：** Vidau Mobile / Cloud Agent（云端执行，对标 Manus Skills + MCP + Sandbox）  
**范围：** 手机直连云端 Agent；选 Skill/Expert → 云端执行 → MCP / 沙箱工具回传结果  
**工作树：** `.worktrees/cloud-agent-p0`（`feature/cloud-agent-p0`）

**关联文档：**

- [OpenVidAU SSO → Cloud LLM Key](./2026-07-11-vidau-openvidau-sso-design.md) — 浏览器 SSO + 计划密钥注入
- [媒体生成实时进度](./2026-07-11-cloud-agent-media-progress-design.md) — Creative 输出媒体 UX
- [桌面 Expert 对齐](./2026-07-13-cloud-agent-desktop-experts-parity-design.md) — Catalog 四 Expert
- [Composer ATTACH](./2026-07-14-mobile-cloud-attach-design.md) — 相册/视频/URL 输入附件
- [会话云存储与历史](./2026-07-14-mobile-cloud-session-history-design.md) — 列表 / 回放 / 删除
- 桌面 Expert 实现参考：`desktop-app/vidau_cli/experts.py`、`desktop-app/experts/catalog.json`

---

## 1. 目标

### 1.1 产品目标

让用户在手机上选择 Skill / Expert，由**云端**完成与桌面 Vidau Agent 对等的任务执行：加载技能说明书、调用远程 MCP 业务能力，并在需要时于隔离沙箱中使用 file / terminal / browser / code_execution，流式返回进度与结果。

### 1.2 成功标准

1. 用户登录后可浏览并启用 Skill / Expert（对齐桌面 Experts 卡片信息：Skills、Tools、MCP、状态）。
2. 新会话可选择 Expert 或 Skill；选择作用于该云端会话。
3. 纯远程 MCP 型任务（如 Creative 主路径 / TikTok Ads）可在**不分配沙箱**时完成。
4. 需要本机类能力的任务可自动或按 Expert 策略分配沙箱，并完成与桌面对等的工具调用。
5. 手机端流式展示 assistant / tool progress / done；**会话历史落在云端并可回看、可继续聊**。
6. 多用户并发时会话隔离（一活跃沙箱会话一 VM）；满载时有明确排队或降级，不串数据。
7. （P0 增补）Composer 可 ATTACH 相册图/视频/URL；Creative 参考素材由服务端桥接，App 不持 MCP Key。
8. （P0 增补）OpenVidAU SSO 登录后 LLM Key 仅留在 Cloud Agent 主机，Expert tool-calling 可用。

---

## 2. 已锁定决策

| 议题 | 决策 |
|---|---|
| 执行位置 | **云端**；不转发到用户桌面 |
| 能力目标 | **完整复刻桌面执行面**（Skill + MCP + 本机 toolsets） |
| Skill | Playbook（`SKILL.md` 等）；渐进加载；注入 system prompt |
| MCP | Data Pipeline；经云端 MCP Gateway 代理；声明式 `requires_mcp` |
| 沙箱 | 承接桌面 `file` / `terminal` / `browser` / `code_execution` 及 Skill 脚本 |
| 开箱策略 | **按需**：纯 MCP 会话可不分配 VM；调用本机类工具或 Expert 策略要求时再分配 |
| 隔离模型 | **一活跃沙箱会话一 microVM**（推荐 Firecracker 类）；**Dev** 可用 `local` 目录沙箱 |
| 移动端 | Flutter（iOS + Android）；Cloud / Link **双模式可切换** |
| 鉴权 | OpenVidAU 浏览器 SSO（经 Cloud Agent 代理）+ 会话 token；Key 不进 Flutter |
| 会话存储 | **云端 SQLite 为权威源**（对齐桌面 `state.db` 思路；与 Mobile Link「Gateway 不存正文」不同） |
| 输入附件 | HTTP 先上传拿 ref，再 WS `attachment_ids`；Creative 服务端桥接 HTTPS |
| 与 Mobile Link | **并行产品轨**；本方案不依赖电脑在线 |

---

## 3. 产品概念

### 3.1 三层能力（对齐桌面与 Manus）

| 层 | 含义 | 云端落点 |
|---|---|---|
| **Skill** | 怎么做（工作流说明书） | Skill Catalog → 会话 prompt（服务器 `data/skills/`） |
| **MCP** | 连哪里（外部业务/数据） | MCP Gateway → 远程 MCP → 业务 API |
| **Sandbox** | 在哪跑本机动作 | Session Sandbox（microVM 或 Dev 本地目录）内的 file/terminal/browser/code |

桌面 Expert 是这三层的**打包配置**（见桌面 `experts` catalog）。云端复用同一打包模型，执行面从「用户电脑」改为「云端 Runtime + 可选沙箱」。

### 3.2 Expert vs Skill

| | Expert | Skill |
|---|---|---|
| 用户感知 | 人设/专家卡片（如 TikTok Ads Specialist） | 可单独启用的能力包 |
| 内容 | `skills` + `toolsets` + `mcp_servers` + `activation_prompt` | `SKILL.md` + 可选资源/脚本 |
| 会话行为 | 一次选择激活整包 | 可多选或由 Expert 带入 |

### 3.3 首发 Expert（对齐桌面）

| Expert | P0 产品态 |
|---|---|
| **Creative** | 可安装、可会话；Skill 全量；媒体进度 + ATTACH 参考图桥接 |
| **TikTok Ads** | 可安装、可会话；MCP Key 软缺失仍可 Skill 问答 |
| **GEO** | 可安装、可会话；MCP `geo.vidau.ai` |
| **Social** | 卡片上架，`coming_soon`，不可 Install / 开聊 |

### 3.4 哪些需要沙箱 VM

| 能力 | 需要沙箱？ | 说明 |
|---|---|---|
| Skill 文本注入 | 否 | 仅 prompt |
| 远程 MCP | 否 | Gateway 代理 HTTP/SSE |
| vision / image_gen / tts 等云 API | 否 | 直接调云服务 / Creative MCP |
| web 搜索/抓取 | 可不进 VM | 可做成宿主机托管工具 |
| file | **是** | 会话工作区 |
| terminal / process | **是** | shell |
| browser | **是** | Chromium 等 |
| code_execution | **是** | 解释器 |
| Skill 内需执行的脚本 | **是** | 经 terminal/code 在 VM 内跑 |

**Expert 完整复刻含义：**

| Expert 类型 | 无沙箱 | 有沙箱 |
|---|---|---|
| TikTok Ads / Creative / GEO（主路径 MCP） | 主路径可用 | 与桌面边角能力（file/terminal）对齐 |
| Social / Code Review / 文档处理 | **不能完整** | **必须** |

---

## 4. 用户体验

### 4.1 主路径

```text
登录（OpenVidAU 浏览器 SSO → Cloud Agent 会话 + LLM Key）
  → Experts 市场（浏览、Install、看 MCP / Coming soon）
  → 新会话：点 Expert → POST /v1/sessions → 云端聊天
  → 若缺 MCP 凭证 → 配置 Key（软提示；TikTok 等可不阻断 Skill）
  → 聊天：发文案；可选 ATTACH 图/视频/URL；Creative 可点比例 Chip
  → 云端执行（LLM + MCP 和/或沙箱工具；媒体进度媒体气泡）
  → 手机流式展示进度与结果
  → Experts「历史会话」→ 回放气泡 → WS 重连继续聊；可删除
```

### 4.2 关键界面

| 界面 | 要点 |
|---|---|
| 登录 | 外置浏览器 SSO；回 App 轮询票据（勿依赖生产 App Universal Link） |
| Experts / Skills 市场 | 对齐桌面卡片：描述、Skills、MCP、Ready / Needs setup / Coming soon；**历史入口** |
| 历史会话 | Expert 名、时间、最近预览；左滑/长按删除；点进回放并继续聊 |
| 会话 Composer | 标明「云端执行」；`+` ATTACH Sheet（相册图/视频/URL）；pending chips；`@` 本会话附件 |
| 用户气泡 | 文本 + 内嵌图/视频占位/链接行（历史回放 P0 以文本为主） |
| Creative 澄清 | 首次助手回复后展示 `9:16` / `1:1` / `16:9` 等快捷 Chip |
| 授权 | MCP Key 配置；Creative/TikTok/GEO 按 Expert 声明 |
| 执行态 | 加载 Skill / 调用 MCP / 沙箱启动 / 工具运行 / 媒体 Shimmer 进度 |
| 会话列表 | 云端权威；App 不做本地会话库 |

### 4.3 状态文案（产品侧）

| 状态 | 用户可见含义 |
|---|---|
| Ready | 依赖已满足，可用于新会话 |
| Needs setup | 缺 Skill 安装记录、MCP 未配置或未授权 |
| Coming soon | 本期不可开聊（如 Social） |
| Sandbox starting | 正在准备云端执行环境（首次本机类工具时） |
| Queued | 沙箱并发已满，排队中 |
| Needs auth | 需要补齐 MCP 凭证或重新 SSO |

---

## 5. 技术架构（产品级）

### 5.1 拓扑

```text
Flutter App
    │  HTTPS + WSS（会话 token）
    ▼
Cloud Agent（本机 Dev / 未来云托管）
    ├─ Auth / OpenVidAU SSO 代理     ← 登录票据 + bootstrap LLM Key
    ├─ Session / Transcript / Attachments  ← SQLite + 会话目录文件
    ├─ Skill / Expert Catalog
    ├─ Agent Runtime                   ← LLM tool loop + prompt 组装
    ├─ MCP Gateway + Credential Vault  ← 远程 MCP（不进 VM）
    ├─ Creative Bridge                 ← 附件 → 上传指令 / base64 → HTTPS URL
    ├─ Media Hub / Tracker             ← media.placeholder|progress|ready
    └─ Sandbox Provider
            │  create / pause / resume / destroy（产品契约）
            ▼
       Dev: local 目录 | 生产: microVM 池（Firecracker / 托管）
```

### 5.2 调用关系（Skill → MCP / 沙箱）

```text
选 Expert
  → 解析绑定：skills[]、requires_mcp[]、toolsets[]、needs_sandbox 策略
  → 检查 MCP 凭证（可软缺失）
  → Agent Runtime：
        activation_prompt + 已安装 SKILL.md → system prompt
        挂载 mcp_* 工具（Gateway）
        若策略或工具调用需要 → 分配/唤醒沙箱 → 挂载本机类工具
        Creative 生成工具前：按需桥接 session attachments → reference_* URLs
  → 模型按 Skill 指引调用 mcp_* 或沙箱工具
  → 流式事件回手机（含 media.*）
```

相对桌面「仅靠 prompt 软耦合」，云端要求 **声明式绑定**：Skill/Expert manifest 写明 `requires_mcp`；缺依赖时产品态失败或软提示，而不是静默降智。

### 5.3 沙箱生命周期

1. `session.create`：若 Expert 标记「创建即需要沙箱」→ 立即分配；否则延迟。  
2. 首次本机类 tool call → 懒加载分配（若尚未分配）。  
3. 空闲超时 → pause（降成本）。  
4. 会话结束 / TTL → destroy；必要产物写入对象存储并在会话中可下载。  
5. **Dev Profile：** `sandbox_provider=local`，会话工作区落盘，无 microVM。

### 5.4 多租户与压力

| 维度 | 策略 |
|---|---|
| 隔离 | 一活跃沙箱会话一 VM；禁止跨会话磁盘挂载 |
| 配额 | 每用户并发沙箱上限（建议默认 1–2）；全局并发上限 |
| 满载 | 排队 + 可感知状态；可选降级为「仅 MCP 能力」并提示 |
| 成本 | 按 VM 运行时长计；纯 MCP 会话默认不开 VM |

**量级参考（托管 Firecracker 类公开价，非合同价）：** 约 $0.13–0.17 /（2 vCPU·2–4 GiB·小时）。成本随「同时未 pause 的 VM 数 × 时长」增长，而非注册用户数。自建需运维评估裸金属/KVM、密度与安全（另附运维咨询提纲）。

### 5.5 部署选项（产品决策输入）

| 选项 | 适用 |
|---|---|
| 托管沙箱（E2B 等） | 快验证、少运维；注意数据驻留与单价 |
| 自建 Firecracker 集群 | 可控、大规模可能更优；需 KVM/裸金属与安全评审 |
| 普通多租户 Docker | **不推荐**作为完整复刻的默认隔离方案 |
| Dev local 目录 | **仅本机联调**；禁止带进生产 |

首发建议：**业务与 Runtime 自建；沙箱可先托管或小规模自建试点**，以运维结论为准。当前工程默认 **Dev local**。

---

## 6. 移动端模块

| 模块 | 职责 | P0 现状 |
|---|---|---|
| `auth` | OpenVidAU SSO、会话 token、安全存储 | 已接 Cloud 代理 SSO |
| `experts` | 市场、Install、MCP 状态、历史入口 | Creative / TikTok / GEO / Social |
| `chat` | 发送、流式渲染、ATTACH、媒体卡、澄清 Chip | Cloud 聊天页已交付 |
| `credentials` | MCP Key 配置 | 已有 |
| `session` | 云端会话列表、打开回放、删除、WS 重连 | 已交付 |
| `attachments`（客户端） | 上传 / 列表 / 删除 / `@` | 已交付 |
| `local_cache` | UI 缓存（权威仍在云端） | 不做会话权威库 |

**不做：** 设备列表（Cloud 模式）、连电脑执行 Skill、直连上游 MCP、沙箱运维界面。

---

## 7. 服务端模块

| 模块 | 职责 | P0 现状 |
|---|---|---|
| Skill / Expert Catalog | 元数据、版本、绑定、`needs_sandbox` | `catalog.json` + Install |
| Session / Transcript | 会话 CRUD、消息持久化、列表/删除 | SQLite + REST |
| Attachments | 会话图/视频/URL 存储与下载 | HTTP + 磁盘 |
| Agent Runtime | LLM tool loop + Skill 注入 | `agent_loop` |
| MCP Gateway | 远程 MCP SSE / mock | 已有 |
| Credential Vault | 用户级 MCP 密钥 | 已有 |
| Creative Bridge | 附件 → Creative HTTPS 参考 URL | 已有 |
| Media Hub / Tracker | 生成占位与进度推送 | 已有 |
| Sandbox Orchestrator | VM 生命周期 | Dev=`local`；生产待接 |
| OpenVidAU SSO | 登录票据 / poll / bootstrap Key | 已有 |

---

## 8. 协议要点（产品契约）

### 8.1 会话创建

`POST /v1/sessions`

```json
{
  "expert_id": "vidau-creative-agent-oneclick"
}
```

响应可含：`session_id`、`status`（`ready` | `needs_setup` | …）、`missing_credentials[]`、`expert_name`、`llm_mode`、`mcp_mode`。

### 8.2 会话历史（云端权威）

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/v1/sessions` | 列表（`updated_at` 倒序、preview、message_count） |
| `GET` | `/v1/sessions/{id}/messages` | 打开聊天前回放 |
| `DELETE` | `/v1/sessions/{id}` | 删会话 + 消息 + 尽力清附件目录 |

打开历史：HTTP 拉消息 → 填气泡 → WS 连接 → 可继续 `chat.send`。

### 8.3 附件

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/v1/sessions/{id}/attachments` | JSON URL 或 multipart `file` |
| `GET` | `/v1/sessions/{id}/attachments` | `@` 补全源 |
| `DELETE` | `/v1/sessions/{id}/attachments/{aid}` | 删除 |
| `GET` | `/v1/sessions/{id}/attachments/{aid}/file` | 文件下载（需鉴权） |

### 8.4 实时事件（示意）

| type | 用途 |
|---|---|
| `chat.user` / `chat.assistant` | 消息；`chat.user` 可带 `attachments[]` |
| `chat.send`（客户端→服务端） | `{ content, attachment_ids? }`；允许仅附件 |
| `chat.progress` | 工具/日志进度（可节流） |
| `tool.mcp` | MCP 调用开始/结束（可折叠展示） |
| `media.placeholder` / `media.progress` / `media.ready` / `media.failed` | Creative 等媒体生成 |
| `sandbox.status` | starting / ready / paused / queued / error |
| `chat.done` / `chat.error` | 本轮结束 |

### 8.5 Manifest 字段（Skill/Expert，示意）

```yaml
id: tiktok-ads-skills
requires_mcp: [tiktok-ads-agent]
toolsets: [web, file, terminal]   # 完整复刻时声明
sandbox_policy: on_demand         # never | on_demand | always
needs_sandbox: false              # 预留；与 policy 一致即可
```

---

## 9. 分期建议

| 阶段 | 交付 | 沙箱 |
|---|---|---|
| **P0（当前）** | SSO、Catalog 四 Expert、会话 CRUD/历史、ATTACH、Creative 桥接与媒体进度、Flutter 云聊 | Dev `local`；生产可不分配 |
| **P1** | 按需沙箱 file/terminal；历史附件预览；会话标题/筛选；上传重试 | 托管或小规模自建 |
| **P2** | browser + Social 主路径；配额/排队/pause | 扩容与密度优化 |
| **P3** | 与桌面 catalog 持续同步、团队 Skill 库、治理 | 按运维结论扩集群 |

P0 已验证「选 Expert → SSO LLM → 调 MCP / Creative」产品闭环；完整复刻桌面以 P1–P2 沙箱为准。

### 9.1 P0 已交付摘要（相对原文的增量）

| 能力 | 状态 |
|---|---|
| OpenVidAU SSO + LLM bootstrap | 已交付（Dev） |
| Experts 市场 + Install（含 GEO / Social coming_soon） | 已交付 |
| 云端聊天 WS + agent loop | 已交付 |
| 会话列表 / 消息回放 / 删除 | 已交付 |
| ATTACH 图/视频/URL + `@` + 气泡预览 | 已交付 |
| Creative 参考 URL 桥接 | 已交付 |
| 媒体生成进度事件 | 已交付 |
| 生产 Firecracker 多租户沙箱 | **未做**（Dev local） |
| Social 完整执行 | **未做** |
| 历史气泡内完整附件回放 | **未做**（P1） |

---

## 10. 风险与应对

| 风险 | 应对 |
|---|---|
| 沙箱成本随并发线性上升 | 按需开箱、idle pause、每用户并发上限、MCP-only 不开 VM |
| 自建无 KVM/裸金属 | P1 先托管；并行运维评估 |
| MCP 凭证泄露进沙箱盘 | Vault 短时注入；禁持久落盘；审计 |
| 与桌面行为不一致 | 同名 toolsets 契约测试；官方 Expert 回归集 |
| 用户以为「连了电脑」 | UI 明确「云端执行」；Mobile Link 入口分离 |
| SSO 深链打开错误 App | 用 `vidau-desktop` client 配置；登录后切回 Agent，勿点「打开 App」 |
| 真机缩略图 401 | 附件文件接口需鉴权；后续用带 token 的图片加载或短时签名 URL |
| `PUBLIC_BASE_URL` 误用 127.0.0.1 | 真机须设 LAN IP，否则 LLM/Creative 上下文 URL 不可达 |

---

## 11. 验收清单（产品）

### P0（MCP 云端闭环 + 会话/附件）

- [x] 市场可展示官方 Expert（Creative / TikTok / GEO；Social coming_soon），状态正确  
- [x] SSO 后 Expert 会话可走真实 LLM + MCP（依赖本机配置与 Key）  
- [x] 手机流式看到进度与最终结果  
- [x] 云端历史可列表、回看、继续聊、删除  
- [x] ATTACH 图/视频/URL；Creative 可作参考（服务端桥接）  
- [x] 电脑离线不影响该路径  
- [ ] 生产多租户沙箱与配额（延后 P1+）  
- [ ] 附件预览鉴权体验在真机验收通过  

### P1（沙箱按需）

- [ ] 触发 file/terminal 时出现沙箱启动态，随后工具成功执行  
- [ ] 纯 MCP 回合不创建 VM（可观测指标）  
- [ ] 两用户并发互不可见工作区  
- [ ] 历史回放含附件缩略图；会话标题/按 Expert 筛选  

### P2（完整复刻关键路径）

- [ ] browser 类 Expert 主路径可用  
- [ ] 满载排队状态对用户可见且可恢复  

---

## 12. 本地开发部署（Dev Profile）

本机（含 macOS 笔记本）用于**开发与联调**，不作为生产多租户沙箱集群。

### 12.1 结论

| 组件 | 本机是否可行 |
|---|---|
| Catalog / Agent Runtime / MCP Gateway / 会话库 | **可行**（已落地） |
| Flutter 连本机 API | **可行**（`CLOUD_HOST` / `GATEWAY_HOST` = LAN IP） |
| Firecracker microVM（生产形态） | **macOS 不可行**（需 Linux KVM） |
| 开发用沙箱降级 | **可行**（`local`） |

### 12.2 推荐本机拓扑

```text
开发机（macOS / Linux）
  ├─ cloud_agent（Auth + Session + Catalog + Runtime + Attachments）
  ├─ MCP Gateway → 远程 MCP（或 mock）
  ├─ SQLite data/sessions.db（transcript）
  ├─ data/sessions/{session_id}/attachments/
  ├─ Sandbox Provider：local（本机工作区目录）
  └─ Flutter App → http://<LAN_IP>:8787
       CLOUD_AGENT_OPENVIDAU_CLIENT_APP=vidau-desktop   # SSO 建议
       CLOUD_AGENT_PUBLIC_BASE_URL=http://<LAN_IP>:8787
```

生产 Profile 将 `Sandbox Provider` 换为 `firecracker` / 托管 E2B；**对外 API（create/pause/destroy）保持不变**。

### 12.3 本机实施顺序

1. **P0：** `sandbox=local|none`，Runtime + MCP + SSO + 会话历史 + ATTACH — **当前重点**。  
2. **P1-dev：** 强化 file/terminal 与历史附件。  
3. **预发/生产：** Linux + Firecracker 或托管；本机不再承担多租户隔离。

### 12.4 本机明确不做

- 用本机 Firecracker 模拟生产密度与隔离证明  
- 多用户共用电脑当生产沙箱宿主机  
- 将 `dev_local`（无隔离）配置带进生产  

### 12.5 常用启动

```bash
cd .worktrees/cloud-agent-p0/cloud_agent
CLOUD_AGENT_OPENVIDAU_CLIENT_APP=vidau-desktop \
CLOUD_AGENT_PUBLIC_BASE_URL=http://<LAN_IP>:8787 \
./scripts/run_dev.sh

cd .worktrees/cloud-agent-p0
flutter run --dart-define=EXECUTION_MODE=cloud --dart-define=CLOUD_HOST=<LAN_IP>
```

---

## 13. 待决事项（审阅时确认）

| # | 议题 | 现状 |
|---|---|---|
| 1 | **P0 首发 Expert** | **已定：Creative + TikTok + GEO**；Social coming_soon |
| 2 | **沙箱供应（生产）** | 仍待运维；**开发默认 `local`** |
| 3 | **每用户默认并发沙箱上限** | 建议 1（生产生效时） |
| 4 | **云端会话保留时长与配额** | 仍待定（合规/存储） |
| 5 | **App 内是否保留 Mobile Link** | **已定：双模式可切换** |
| 6 | **附件文件鉴权 UX** | 待真机方案（signed URL 或带 Header 加载） |
| 7 | **会话标题 / 搜索** | 明确 P1 |

---

## 14. 参考

- Manus：[Agent Skills](https://manus.im/features/agent-skills)、[Skills 与 MCP](https://manus.im/blog/manus-skills)、[Sandbox](https://manus.im/blog/manus-sandbox)  
- 沙箱成本量级：[E2B Pricing](https://e2b.dev/pricing)（公开价，仅作量级参考）  
- 桌面：`vidau_cli/experts.py`、`experts/catalog.json`、`toolsets.py`、`tools/mcp_tool.py`；会话存储 `website/docs/developer-guide/session-storage.md`  
- 架构分析 Canvas：`canvases/cloud-skills-mcp-architecture.canvas.tsx`  
- 实现计划：`docs/superpowers/plans/2026-07-14-mobile-cloud-attach.md`、`docs/superpowers/plans/2026-07-14-mobile-cloud-session-history.md`  

---