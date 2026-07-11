# Vidau Cloud Agent 产品设计文档

**日期：** 2026-07-11  
**状态：** 待审阅  
**产品：** Vidau Mobile / Cloud Agent（云端执行，对标 Manus Skills + MCP + Sandbox）  
**范围：** 手机直连云端 Agent；选 Skill/Expert → 云端执行 → MCP / 沙箱工具回传结果  

**关联文档：**

- [Mobile Link 一期](./2026-07-10-vidau-mobile-link-phase1-design.md) — 手机连电脑执行（**并行产品轨，本方案不依赖**）
- 桌面 Expert 实现参考：`desktop-app/vidau_cli/experts.py`、`desktop-app/experts/catalog.json`

---

## 1. 目标

### 1.1 产品目标

让用户在手机上选择 Skill / Expert，由**云端**完成与桌面 Vidau Agent 对等的任务执行：加载技能说明书、调用远程 MCP 业务能力，并在需要时于隔离沙箱中使用 file / terminal / browser / code_execution，流式返回进度与结果。

**不要求**用户电脑在线；**不经**桌面 Agent 转发。

### 1.2 成功标准

1. 用户登录后可浏览并启用 Skill / Expert（对齐桌面 Experts 卡片信息：Skills、Tools、MCP、状态）。
2. 新会话可选择 Expert 或 Skill；选择作用于该云端会话。
3. 纯远程 MCP 型任务（如 TikTok Ads / Creative 主路径）可在**不分配沙箱**时完成。
4. 需要本机类能力的任务可自动或按 Expert 策略分配沙箱，并完成与桌面对等的工具调用。
5. 手机端流式展示 assistant / tool progress / done；会话历史落在云端。
6. 多用户并发时会话隔离（一活跃沙箱会话一 VM）；满载时有明确排队或降级，不串数据。

### 1.3 明确不做（本阶段）

- 手机连接用户电脑执行（见 Mobile Link；本方案不依赖）
- 社区不可信 Skill 市场的完整治理（可预留，首发以官方 Skill/Expert 为主）
- 桌面 GUI 与云端会话的双向实时同屏（可后续）
- 语音、推送、多 Expert 同会话深度编排（可后续）

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
| 隔离模型 | **一活跃沙箱会话一 microVM**（推荐 Firecracker 类） |
| 移动端 | Flutter（iOS + Android） |
| 鉴权 | 复用 Vidau / Nous Portal SSO + JWT |
| 会话存储 | **云端为权威源**（与 Mobile Link「Gateway 不存正文」不同） |
| 与 Mobile Link | **并行产品轨**；本方案不依赖电脑在线 |

---

## 3. 产品概念

### 3.1 三层能力（对齐桌面与 Manus）

| 层 | 含义 | 云端落点 |
|---|---|---|
| **Skill** | 怎么做（工作流说明书） | Skill Catalog → 会话 prompt |
| **MCP** | 连哪里（外部业务/数据） | MCP Gateway → 远程 MCP → 业务 API |
| **Sandbox** | 在哪跑本机动作 | Session Sandbox（microVM）内的 file/terminal/browser/code |

桌面 Expert 是这三层的**打包配置**（见桌面 `experts` catalog）。云端复用同一打包模型，执行面从「用户电脑」改为「云端 Runtime + 可选沙箱」。

### 3.2 Expert vs Skill

| | Expert | Skill |
|---|---|---|
| 用户感知 | 人设/专家卡片（如 TikTok Ads Specialist） | 可单独启用的能力包 |
| 内容 | `skills` + `toolsets` + `mcp_servers` + `activation_prompt` | `SKILL.md` + 可选资源/脚本 |
| 会话行为 | 一次选择激活整包 | 可多选或由 Expert 带入 |

### 3.3 哪些需要沙箱 VM

| 能力 | 需要沙箱？ | 说明 |
|---|---|---|
| Skill 文本注入 | 否 | 仅 prompt |
| 远程 MCP | 否 | Gateway 代理 HTTP/SSE |
| vision / image_gen / tts 等云 API | 否 | 直接调云服务 |
| web 搜索/抓取 | 可不进 VM | 可做成宿主机托管工具 |
| file | **是** | 会话工作区 |
| terminal / process | **是** | shell |
| browser | **是** | Chromium 等 |
| code_execution | **是** | 解释器 |
| Skill 内需执行的脚本 | **是** | 经 terminal/code 在 VM 内跑 |

**Expert 完整复刻含义：**

| Expert 类型 | 无沙箱 | 有沙箱 |
|---|---|---|
| TikTok Ads / Creative（主路径 MCP） | 主路径可用 | 与桌面边角能力（file/terminal）对齐 |
| Social / Code Review / 文档处理 | **不能完整** | **必须** |

---

## 4. 用户体验

### 4.1 主路径

```text
登录（SSO）
  → Skills / Experts 市场（浏览、启用、看依赖：MCP / 是否可能开沙箱）
  → 新会话：选择 Expert 或 Skill（可「无专家」）
  → 若缺 MCP 凭证 → 授权页（API Key / OAuth）→ 返回会话
  → 聊天：发送任务
  → 云端执行（MCP 和/或沙箱工具）
  → 手机流式展示进度与结果
  → 历史在云端可回看
```

### 4.2 关键界面

| 界面 | 要点 |
|---|---|
| Experts / Skills 市场 | 对齐桌面卡片：描述、tags、Skills、Tools、MCP、Ready / Needs setup |
| 会话 Composer | Expert/Skill 选择器；文案明确「云端执行」 |
| 授权 | MCP 未就绪时阻断执行并引导授权，避免空跑 |
| 执行态 | 区分：加载 Skill / 调用 MCP / 沙箱启动中 / 工具运行中 / 等待确认 |
| 会话列表 | 云端会话；展示所用 Expert、是否曾用沙箱（可选） |

### 4.3 状态文案（产品侧）

| 状态 | 用户可见含义 |
|---|---|
| Ready | 依赖已满足，可用于新会话 |
| Needs setup | 缺 Skill 安装记录、MCP 未配置或未授权 |
| Sandbox starting | 正在准备云端执行环境（首次本机类工具时） |
| Queued | 沙箱并发已满，排队中 |
| Needs auth | 需要补齐 MCP 凭证 |

---

## 5. 技术架构（产品级）

### 5.1 拓扑

```text
Flutter App
    │  HTTPS + WSS（JWT）
    ▼
Cloud API
    ├─ Auth / Session Service          ← 会话与 transcript（云端权威）
    ├─ Skill / Expert Catalog
    ├─ Agent Runtime                   ← LLM tool loop + prompt 组装
    ├─ MCP Gateway + Credential Vault  ← 远程 MCP（不进 VM）
    └─ Sandbox Orchestrator
            │  create / pause / resume / destroy
            ▼
       microVM 池（Firecracker 类）
       内含：file / terminal / browser / code 适配器
```

### 5.2 调用关系（Skill → MCP / 沙箱）

```text
选 Expert/Skill
  → 解析绑定：skills[]、requires_mcp[]、toolsets[]、needs_sandbox 策略
  → 检查 MCP 凭证；失败 → needs_auth
  → Agent Runtime：
        activation_prompt + 预加载 SKILL.md → system prompt
        挂载 mcp_* 工具（Gateway）
        若策略或工具调用需要 → 分配/唤醒沙箱 → 挂载本机类工具
  → 模型按 Skill 指引调用 mcp_* 或沙箱工具
  → 流式事件回手机
```

相对桌面「仅靠 prompt 软耦合」，云端要求 **声明式绑定**：Skill/Expert manifest 写明 `requires_mcp`；缺依赖时产品态失败，而不是静默降智。

### 5.3 沙箱生命周期

1. `session.create`：若 Expert 标记「创建即需要沙箱」→ 立即分配；否则延迟。  
2. 首次本机类 tool call → 懒加载分配（若尚未分配）。  
3. 空闲超时 → pause（降成本）。  
4. 会话结束 / TTL → destroy；必要产物写入对象存储并在会话中可下载。  

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

首发建议：**业务与 Runtime 自建；沙箱可先托管或小规模自建试点**，以运维结论为准。

---

## 6. 移动端模块

| 模块 | 职责 |
|---|---|
| `auth` | Portal SSO、JWT、安全存储 |
| `skills` / `experts` | 市场、启用、依赖与状态 |
| `chat` | Composer 选择、发送、流式渲染、工具/沙箱状态 |
| `credentials` | MCP 授权与绑定状态 |
| `session` | 云端会话列表、重连、历史 |
| `local_cache` | UI 缓存（权威仍在云端） |

**不做：** 设备列表、连电脑、本地执行 Skill、直连上游 MCP、沙箱运维界面。

---

## 7. 服务端模块

| 模块 | 职责 |
|---|---|
| Skill / Expert Catalog | 元数据、版本、绑定、`needs_sandbox` 策略 |
| Session / Transcript | 云端会话 CRUD 与消息持久化 |
| Agent Runtime | 对齐桌面 `_make_agent` + `resolve_expert_activation` 的云端形态 |
| MCP Gateway | 连接池、鉴权注入、限流、审计 |
| Credential Vault | 用户级 MCP 密钥 |
| Sandbox Orchestrator | VM 生命周期、预热池、配额、排队 |
| Tool Bridge | 桌面同名 toolsets 在沙箱内的适配 |

---

## 8. 协议要点（产品契约）

### 8.1 会话创建（示意）

```json
{
  "expert_id": "tiktok-ads-agent",
  "skill_ids": [],
  "model": "…",
  "locale": "zh"
}
```

响应可含：`session_id`、`status`（`ready` | `needs_auth` | `sandbox_starting`）、`missing_credentials[]`。

### 8.2 实时事件（示意）

| type | 用途 |
|---|---|
| `chat.user` / `chat.assistant` | 消息 |
| `chat.progress` | 工具/日志进度（可节流） |
| `tool.mcp` | MCP 调用开始/结束（可折叠展示） |
| `sandbox.status` | starting / ready / paused / queued / error |
| `chat.done` / `chat.error` | 本轮结束 |

### 8.3 Manifest 字段（Skill/Expert，示意）

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
| **P0** | 云端会话 + Catalog + 1 个 MCP Expert 端到端（建议 TikTok Ads 或 Creative）+ Flutter 聊天/授权 | 可不分配或仅预留接口 |
| **P1** | 按需沙箱 + file/terminal；第二个 Expert | 托管或小规模自建 |
| **P2** | browser + Social 类 Expert；配额/排队/pause 成本优化 | 扩容与密度优化 |
| **P3** | 与桌面 catalog 持续同步、团队 Skill 库、治理 | 按运维结论扩集群 |

P0 即可验证「选 Skill → 调 MCP」产品闭环；完整复刻桌面以 P1–P2 沙箱为准。

---

## 10. 风险与应对

| 风险 | 应对 |
|---|---|
| 沙箱成本随并发线性上升 | 按需开箱、idle pause、每用户并发上限、MCP-only 不开 VM |
| 自建无 KVM/裸金属 | P1 先托管；并行运维评估 |
| MCP 凭证泄露进沙箱盘 | Vault 短时注入；禁持久落盘；审计 |
| 与桌面行为不一致 | 同名 toolsets 契约测试；官方 Expert 回归集 |
| 用户以为「连了电脑」 | UI 明确「云端执行」；Mobile Link 入口分离 |

---

## 11. 验收清单（产品）

### P0（MCP 云端闭环）

- [ ] 市场可展示至少 1 个官方 Expert，状态 Ready / Needs setup 正确  
- [ ] 授权 MCP 后，新会话选择该 Expert 可完成真实业务调用（非 mock）  
- [ ] 手机流式看到进度与最终结果；云端可回看历史  
- [ ] 电脑离线不影响该路径  

### P1（沙箱按需）

- [ ] 触发 file/terminal 时出现沙箱启动态，随后工具成功执行  
- [ ] 纯 MCP 回合不创建 VM（可观测指标）  
- [ ] 两用户并发互不可见工作区  

### P2（完整复刻关键路径）

- [ ] browser 类 Expert 主路径可用  
- [ ] 满载排队状态对用户可见且可恢复  

---

## 12. 本地开发部署（Dev Profile）

本机（含 macOS 笔记本）用于**开发与联调**，不作为生产多租户沙箱集群。

### 12.1 结论

| 组件 | 本机是否可行 |
|---|---|
| Catalog / Agent Runtime / MCP Gateway / 会话库 | **可行** |
| Flutter 连本机 API | **可行**（`localhost` 或局域网 IP） |
| Firecracker microVM（生产形态） | **macOS 不可行**（需 Linux KVM） |
| 开发用沙箱降级 | **可行**（见下） |

### 12.2 推荐本机拓扑

```text
开发机（macOS / Linux）
  ├─ cloud-agent API（Auth + Session + Catalog + Runtime）
  ├─ MCP Gateway → 远程 MCP（或 mock）
  ├─ SQLite / 本地 Postgres（transcript）
  ├─ Sandbox Provider：
  │     dev_local  → 本机工作区目录（无隔离，仅本人）
  │     dev_docker → 一会话一容器（推荐有 Docker 时）
  │     none       → P0 纯 MCP，不分配沙箱
  └─ Flutter App → http(s)://<本机IP>:<port>
```

生产 Profile 将 `Sandbox Provider` 换为 `firecracker` / 托管 E2B；**对外 API（create/pause/destroy）保持不变**。

### 12.3 本机实施顺序

1. **P0：** `sandbox=none`，只跑 Runtime + MCP Gateway，验证选 Expert → 调 MCP。  
2. **P1-dev：** `dev_docker` 或 `dev_local`，验证 file/terminal。  
3. **预发/生产：** Linux + Firecracker 或托管；本机不再承担多租户隔离。

### 12.4 本机明确不做

- 用本机 Firecracker 模拟生产密度与隔离证明  
- 多用户共用电脑当生产沙箱宿主机  
- 将 `dev_local`（无隔离）配置带进生产

---

## 13. 待决事项（审阅时确认）

1. **P0 首发 Expert：** TikTok Ads 还是 Creative Agent？（实现计划默认 **TikTok Ads**，可改）  
2. **沙箱供应（生产）：** 托管 vs 自建（等运维结论）；**开发默认 `none` → `dev_docker`**。  
3. **每用户默认并发沙箱上限：** 建议 1。  
4. **云端会话保留时长与配额**（存储与合规）。  
5. **是否在 App 内同时保留 Mobile Link 入口**（双模式），或云端版独立产品包。（实现计划默认 **双模式入口可切换**）  

---

## 14. 参考

- Manus：[Agent Skills](https://manus.im/features/agent-skills)、[Skills 与 MCP](https://manus.im/blog/manus-skills)、[Sandbox](https://manus.im/blog/manus-sandbox)  
- 沙箱成本量级：[E2B Pricing](https://e2b.dev/pricing)（公开价，仅作量级参考）  
- 桌面：`vidau_cli/experts.py`、`experts/catalog.json`、`toolsets.py`、`tools/mcp_tool.py`  
- 架构分析 Canvas：`canvases/cloud-skills-mcp-architecture.canvas.tsx`  

---

## 附录 A. 给运维的自建咨询提纲（可转发）

**目标一句话：** 云端 Agent 需要「一会话一隔离沙箱」跑 file/terminal/browser；请评估自建 Firecracker 类方案的可行性、周期与成本。

请回复：

1. 现网是否支持 KVM / 裸金属 / 嵌套虚拟化？  
2. 峰值并发 20 / 50 / 100，单台 2c4g，各需多少宿主机与月成本区间？  
3. 安全是否允许多租户跑 Agent 生成代码？沙箱默认能否禁访问内网？  
4. 是否已有 create/pause/resume/destroy 类平台？SLA（创建 P99）目标能否 &lt; 3s（预热）？  
5. 结论：可行 / 有条件 / 不可行；建议自建、先托管后自建、或只托管。  
