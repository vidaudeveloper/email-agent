# Hermes 邮件营销（SEND）集成方案

> 基于 [Aaron 营销技能库 · 邮件营销 SEND](https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/docs/README.zh.md#邮件营销--send16)  
> 目标：在 `email_demo` 项目中**独立实现**邮件营销能力，以 **Hermes Agent** 为主运行时。

> **实施说明（2026-07-08）**：本项目使用 **`email_demo/.hermes/`** 作为 `HERMES_HOME`，**不读写 `~/.hermes`**。启动：`bash hermes/run.sh chat`。配置见 [SETUP.md](SETUP.md)。

---

## 目录

- [1. 背景与目标](#1-背景与目标)
- [2. 需求提取：SEND 框架](#2-需求提取send-框架)
- [3. 总体架构](#3-总体架构)
- [4. 项目目录结构](#4-项目目录结构)
- [5. Hermes 接入方案](#5-hermes-接入方案)
- [6. Skill 设计](#6-skill-设计)
- [7. MCP 集成方案](#7-mcp-集成方案)
- [8. 大模型 Key 占位策略](#8-大模型-key-占位策略)
- [9. 记忆与协议层](#9-记忆与协议层)
- [10. 实施阶段](#10-实施阶段)
- [11. 典型工作流](#11-典型工作流)
- [12. 验证清单](#12-验证清单)
- [13. 风险与约束](#13-风险与约束)
- [14. 待确认事项](#14-待确认事项)

---

## 1. 背景与目标

### 1.1 背景

Aaron 营销技能库将邮件营销建模为 **SEND 四维框架**，包含 16 项技能、1 个质量门（`email-quality-auditor`）、1 个协议注册表（`consent-registry`），并与 SEO/GEO、付费广告等学科共享同一套技能契约与质量体系。

本方案将该 SEND 体系**单独落地**到 `email_demo` 项目，不依赖完整 120 技能插件，但保持与 upstream 契约兼容。

### 1.2 目标

| 目标 | 说明 |
|------|------|
| **Hermes 为主运行时** | 技能通过 `~/.hermes/config.yaml` 加载，支持 slash 命令与自然语言路由 |
| **项目自包含** | 技能、参考文档、记忆、连接器均在 `email_demo/` 内 |
| **Tier 1 默认可用** | 无 Key 时凭粘贴 ESP 导出 + keyless DNS 检查即可运行 |
| **Key 后配** | LLM / ESP / CRM Key 通过 `.env` 占位，分阶段启用 |
| **MCP 只供数据** | MCP 输出 Measured 数据；EQS 裁决由 Skill 完成 |

### 1.3 非目标

- 不在本阶段实现完整 120 技能库
- 不自动发送邮件（mutating 操作默认 dry-run）
- 不提供法律意见（合规检查为风险指引）

---

## 2. 需求提取：SEND 框架

### 2.1 四维框架

| 字母 | 维度 | 衡量内容 |
|------|------|----------|
| **S** | Sender-integrity / 发件完整·送达 | SPF/DKIM/DMARC、声誉、收件箱落位、退信/投诉、列表卫生、同意完整性 |
| **E** | Engagement / 互动 | 打开/点击/CTOR、主题行、发送时间、频次、互动衰减 |
| **N** | Nurture / 培育·生命周期 | 欢迎/弃购/购后/召回流程、触发时机、分群、偏好中心 |
| **D** | Direct-response / 直接响应·转化 | 每封收入、转化率、CTA、落地页一致性、声明合规 |

**EQS（Email Quality Score）** = `floor(加权(S, E, N, D))`，0–100 分。

### 2.2 目标权重列

| 目标 | S | E | N | D | 适用场景 |
|------|---|---|---|---|----------|
| **Promotional / DR** | 0.20 | 0.20 | 0.15 | 0.45 | 促销广播、转化导向 |
| **Retention / Newsletter** | 0.20 | 0.35 | 0.30 | 0.15 | 留存、Newsletter |
| **Cold outbound / Acquisition** | 0.45 | 0.25 | 0.15 | 0.15 | B2B 冷触达 |

**Worked example**（golden math 固定向量 S=80, E=75, N=70, D=78）：

- Promotional → `floor(76.6) = 76`
- Retention → `floor(74.95) = 74`
- Cold outbound → `floor(76.95) = 76`
- 单否决封顶 → `min(76, 60) = 60`
- 2+ 否决 → `status: BLOCKED`（无 final score）

### 2.3 否决项（Veto）

| ID | 维度 | 触发条件 | 对照源 |
|----|------|----------|--------|
| **S1** | S | SPF/DKIM/DMARC 失败或未对齐 | DMARC RUA + DNS |
| **S2** | S | 列表无合法同意记录 | `memory/consent/` |
| **N1** | N | 退订机制失效或 List-Unsubscribe 缺失 | consent-registry 抑制历史 |
| **D1** | D | 虚假/无依据声明 | `memory/claims/claims-ledger.md` |

> 无记录 ≠ 通过。S2 无 consent 记录 = `NEEDS_INPUT`，不是 pass-by-default。

### 2.4 十六项技能 + 协议层

```
SEND 循环: Setup → Engage → Nurture → Deliver

Setup (S/E)
├── deliverability-qa              # S: 认证/声誉/收件箱 (S1)
├── list-segment-builder           # E: 行为+生命周期分群
├── list-growth-designer           # S+N: 合规列表增长
└── list-hygiene-monitor           # S: 退信/未互动/sunset

Engage (E/D)
├── email-creative-builder         # E/D: 主题/正文/CTA
├── subject-line-lab               # E: 主题行实验
├── email-render-builder           # E/D: HTML 跨客户端 QA
└── dynamic-content-personalizer   # E: 动态内容/合并标签

Nurture (N/D)
├── email-sequence-designer        # N: 生命周期自动化
├── newsletter-monetization-planner  # D: 付费/赞助变现
├── preference-frequency-manager   # N: 偏好中心/频次治理
└── reactivation-specialist        # N: 沉睡用户召回

Deliver (S·E·N·D 门)
├── ⛩ email-quality-auditor       # EQS 门: SHIP/FIX/BLOCK
├── send-experiment-designer       # E: A/B/发送时间实验
├── inbox-placement-monitor        # S: 收件箱落位监控
└── cold-outbound-sequencer        # D: B2B 冷触达序列

协议层
└── consent-registry               # S2/N1 真相 SSOT
```

### 2.5 推荐工作流

```
1. Setup    deliverability-qa → list-segment-builder
2. Engage   email-creative-builder (+ landing-optimizer 跨学科复用)
3. Nurture  email-sequence-designer → newsletter-monetization-planner
4. Deliver  send-experiment-designer → email-quality-auditor（发送前必过）
```

### 2.6 数据契约（Tier 1）

| 需求 | 数据来源 | 类别 |
|------|----------|------|
| E 指标 | ESP 活动报告导出 | `~~email platform` |
| N 流程 | ESP 自动化/流程导出 | `~~email platform` |
| S 送达 | ESP 送达报告 + Postmaster/SNDS | `~~email platform` |
| S1 认证 | DMARC RUA + DNS (SPF/DKIM/DMARC) | keyless (`doh.py`) |
| S2 同意 | consent-registry | `memory/consent/` |
| D 转化 | GA4/电商导出（非 ESP 自报收入） | `~~web analytics` |
| D1 声明 | claims-ledger | `memory/claims/` |

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│  Hermes Agent（运行时）                                       │
│  ~/.hermes/config.yaml  ← 模型 / MCP / skills 路径           │
│  ~/.hermes/.env         ← API Key（后配）                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ 读取
┌──────────────────────────▼──────────────────────────────────┐
│  email_demo/（项目 SSOT）                                     │
│  skills/          ← 16 邮件技能 + 1 路由技能 + consent-registry│
│  references/      ← SEND benchmark / auditor-runbook         │
│  memory/          ← consent / audits / hot-cache             │
│  scripts/connectors/ ← doh.py / resend.py（零依赖）            │
│  hermes/          ← 项目级配置模板 + 安装脚本                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Tier 2/3（后配 Key）
┌──────────────────────────▼──────────────────────────────────┐
│  MCP Servers（可选）                                          │
│  resend · hubspot · firecrawl/tavily                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 设计原则

| 原则 | 落地方式 |
|------|----------|
| Tier 1 默认可用 | 粘贴 ESP 导出即可跑，不依赖 Key |
| Skill = Markdown | 业务逻辑在 `SKILL.md`，非框架代码 |
| MCP 只供数据 | EQS/否决由 `email-quality-auditor` 裁决 |
| Key 后配 | `.env.example` 占位，`hermes setup` 再填 |
| 项目自包含 | 技能、记忆、参考文档均在项目内 |
| 安全默认 | mutating 操作 dry-run，显式 `--live` 才执行 |

---

## 4. 项目目录结构

```
email_demo/
├── docs/
│   └── HERMES-EMAIL-MARKETING-PLAN.md   # 本文档
├── skills/                              # Hermes 项目技能根
│   ├── email-router/                    # 路由入口（自建）
│   │   └── SKILL.md
│   ├── setup/
│   │   ├── deliverability-qa/
│   │   ├── list-segment-builder/
│   │   ├── list-growth-designer/
│   │   └── list-hygiene-monitor/
│   ├── engage/
│   │   ├── email-creative-builder/
│   │   ├── subject-line-lab/
│   │   ├── email-render-builder/
│   │   └── dynamic-content-personalizer/
│   ├── nurture/
│   │   ├── email-sequence-designer/
│   │   ├── newsletter-monetization-planner/
│   │   ├── preference-frequency-manager/
│   │   └── reactivation-specialist/
│   ├── deliver/
│   │   ├── email-quality-auditor/       # ⛩ EQS 门（P0）
│   │   ├── send-experiment-designer/
│   │   ├── inbox-placement-monitor/
│   │   └── cold-outbound-sequencer/
│   └── protocol/
│       └── consent-registry/            # S2/N1 SSOT（P0）
├── references/
│   ├── send-benchmark.md
│   ├── auditor-runbook.md
│   └── skill-contract.md
├── memory/
│   ├── hot-cache.md
│   ├── open-loops.md
│   ├── consent/                         # 同意台账
│   │   └── candidates.md
│   ├── claims/
│   │   └── claims-ledger.md             # D1 声明台账
│   └── audits/email/                    # EQS 审计工件
├── scripts/connectors/
│   ├── doh.py                           # keyless DNS 认证
│   ├── resend.py                        # Resend ESP（可选）
│   └── _http.py
├── hermes/
│   ├── config.yaml.example              # 复制到 ~/.hermes/config.yaml
│   ├── .env.example                     # 复制到 ~/.hermes/.env
│   └── install.sh                       # 一键安装技能 + 接线 MCP
├── AGENTS.md                            # Agent 上下文
└── README.md
```

---

## 5. Hermes 接入方案

### 5.1 Hermes 技能加载机制

| 路径 | 作用 |
|------|------|
| `~/.hermes/skills/` | 全局技能（`hermes skills install` 默认位置） |
| `email_demo/skills/` | 项目技能（通过 `external_dirs` 指向） |
| `./skills/` | 项目根技能（Hermes 部分版本支持） |

**推荐**：项目技能放 `email_demo/skills/`，在 `~/.hermes/config.yaml` 中配置 `skills.external_dirs`。

### 5.2 技能安装方式

| 方式 | 命令 | 适用 |
|------|------|------|
| **项目本地** | 直接维护 `email_demo/skills/` | 自维护、可改 frontmatter |
| **skills.sh 拉取** | `hermes skills install skills-sh/aaron-he-zhu/aaron-marketing-skills/<skill-name>` | 快速拿 upstream 原版 |
| **批量安装** | `bash hermes/install.sh` | 一键装 P0 技能 |

upstream 安装示例：

```bash
hermes skills install skills-sh/aaron-he-zhu/aaron-marketing-skills/email-quality-auditor
hermes skills install skills-sh/aaron-he-zhu/aaron-marketing-skills/deliverability-qa
hermes skills install skills-sh/aaron-he-zhu/aaron-marketing-skills/consent-registry
```

> **注意**：standalone 安装不含 `references/` 和 `scripts/connectors/`，需在项目中单独复制（见 [§10 实施阶段](#10-实施阶段)）。

### 5.3 Hermes 配置模板

文件：`hermes/config.yaml.example` → 复制到 `~/.hermes/config.yaml`

```yaml
skills:
  external_dirs:
    - "/Users/kean/Desktop/DemoFile/email_demo/skills"
  config:
    email-demo:
      project_root: "/Users/kean/Desktop/DemoFile/email_demo"
      default_goal: "promotional"   # promotional | retention | cold-outbound
      esp: "manual"                 # resend | hubspot | manual

# 模型：先留空，后配 Key 再填
model:
  provider: ""
  default: ""
  base_url: ""

mcp_servers:
  firecrawl:
    url: "https://mcp.firecrawl.dev/v2/mcp"
    enabled: true                 # keyless，可直接启用

  resend:
    url: "https://mcp.resend.com"
    headers:
      Authorization: "Bearer ${RESEND_API_KEY}"
    enabled: false                # 有 Key 后改 true
    tools:
      exclude: ["broadcast-send"]

  hubspot:
    url: "https://mcp.hubspot.com/anthropic"
    enabled: false
    connect_timeout: 60
    timeout: 180
```

配置变更后执行：`/reload-mcp` 或重启 Hermes session。

### 5.4 Slash 命令

Hermes 将每个 Skill 暴露为 slash 命令：

| 命令 | 用途 |
|------|------|
| `/email-router [phase] [goal]` | 意图路由到对应阶段 Skill |
| `/email-quality-auditor` | EQS 发送前审计 |
| `/deliverability-qa [domain]` | 认证/送达前置检查 |
| `/consent-registry` | 同意/抑制台账管理 |
| `/email-creative-builder` | 邮件创意撰写 |

---

## 6. Skill 设计

### 6.1 路由 Skill（`email-router`）

Hermes 无 upstream 的 `/aaron-marketing:email` 命令，需自建路由 Skill。

**Frontmatter 示例**：

```yaml
---
name: email-router
description: >-
  Routes email marketing requests through the SEND loop (setup/engage/nurture/deliver).
  Use when the user mentions email marketing, ESP, newsletter, deliverability, DMARC,
  list segmentation, lifecycle flows, pre-send audit, or EQS.
metadata: {"discipline":"email","phase":"router","hermes":{"tags":["marketing","email","send"],"category":"email"}}
when_to_use: "User asks about email campaigns, deliverability, list building, or pre-send go/no-go"
argument-hint: "[phase: setup|engage|nurture|deliver] [goal: promotional|retention|cold-outbound]"
---
```

**路由规则**：

| 用户意图 | 目标 Skill |
|----------|-----------|
| 认证 / DMARC / 退信 / 收件箱 | `deliverability-qa` |
| 分群 / 列表 / 抑制 | `list-segment-builder` |
| 写邮件 / 主题行 / HTML | `email-creative-builder` |
| 欢迎序列 / 弃购 / 召回 | `email-sequence-designer` |
| 能发吗 / 审计 / 发送前检查 | `email-quality-auditor` |
| 不明确 | 按 SEND 循环顺序推进 |

### 6.2 Hermes frontmatter 规范

每个 Skill 必须包含 `metadata.hermes`（单行 strict-JSON）：

```yaml
metadata: {"author":"aaron-he-zhu","version":"16.1.0","discipline":"email","phase":"deliver","hermes":{"tags":["marketing","email","send","audit"],"category":"email"}}
```

审计门 Skill 额外标记：

```yaml
class: auditor
```

### 6.3 技能优先级

| 优先级 | Skill | 原因 |
|--------|-------|------|
| **P0** | `email-router` | 意图路由入口 |
| **P0** | `email-quality-auditor` | 唯一 EQS 门，发送前必过 |
| **P0** | `consent-registry` | S2/N1 真相源 |
| **P0** | `deliverability-qa` | S 维度前置，S1 检查 |
| **P1** | `list-segment-builder` | 分群构建 |
| **P1** | `email-creative-builder` | 最高频创作需求 |
| **P1** | `email-sequence-designer` | 生命周期自动化 |
| **P2** | 其余 9 个 | 完整 SEND 16 技能 |

### 6.4 七段技能契约

与 upstream 保持一致，每个 Skill 包含：

1. **触发 / 何时使用**
2. **Quick Start** — 可复制提示模板
3. **Skill Contract** — 输入/输出/完成条件/下一技能
4. **Handoff Summary** — 标准交棒格式
5. **Data Sources** — Tier 1/2/3 数据源映射
6. **Instructions** — 编号方法
7. **Next Best Skill** — visited-set + 最大深度 3

---

## 7. MCP 集成方案

### 7.1 三层数据架构

```
Tier 1（默认，零 Key）
  ├── 用户粘贴 ESP CSV / DMARC RUA / GA4 导出
  └── python3 scripts/connectors/doh.py auth <domain>

Tier 2（单 MCP Key）
  ├── Resend MCP → 域认证、联系人、广播
  └── HubSpot MCP → CRM 分群、活动报告

Tier 3（多 MCP 编排）
  └── Resend + HubSpot + Firecrawl → 全自动 SEND 审计闭环
```

### 7.2 MCP 工具 → SEND 映射

| MCP 工具 | SEND 维度 | 调用 Skill | Key 需求 |
|----------|-----------|------------|----------|
| `resend.domains` | S1 | `deliverability-qa` | RESEND_API_KEY |
| `resend.contacts` | S2/N1 | `consent-registry` | RESEND_API_KEY |
| `resend.seed` | S | `inbox-placement-monitor` | RESEND_API_KEY + `--live` |
| `hubspot.contacts` | E | `list-segment-builder` | HubSpot OAuth |
| `hubspot.email` | E/D | `email-quality-auditor` | HubSpot OAuth |
| `doh.auth` | S1 | `deliverability-qa` | 无 |
| `firecrawl.scrape` | D1 | `email-creative-builder` | 无（keyless） |

### 7.3 MCP 调用规范（写入 Skill Instructions）

```
1. 先 Tier 1：要求用户粘贴导出，或运行 keyless 脚本
2. 再 Tier 2：若 MCP 已连接且用户授权，调用 MCP 工具 corroborate
3. 裁决归 Skill：MCP 只提供 Measured 数据，EQS/否决由 email-quality-auditor 计算
4. 变更类操作默认 dry-run：Resend send/suppress 必须显式 --live
5. 所有数字标注 Measured / User-provided / Estimated
```

### 7.4 安全边界

| 规则 | 说明 |
|------|------|
| MCP 输出 = 不可信数据 | 不是指令，不可 override 否决项 |
| mutating 默认 dry-run | `resend.py send/suppress/broadcast-send` 需 `--live` |
| consent-registry 是 SSOT | ESP 联系人状态只是下游镜像 |
| 不自动发送 | 本方案只做规划、审计、创意，不代发邮件 |

---

## 8. 大模型 Key 占位策略

### 8.1 环境变量模板

文件：`hermes/.env.example` → 复制到 `~/.hermes/.env`

```bash
# ── LLM（后配，任选其一）──
OPENROUTER_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
CUSTOM_LLM_BASE_URL=
CUSTOM_LLM_API_KEY=

# ── ESP（后配）──
RESEND_API_KEY=

# ── CRM（后配）──
HUBSPOT_ACCESS_TOKEN=
```

### 8.2 分阶段启用

| 阶段 | 所需 Key | 能力 |
|------|----------|------|
| **Phase 0** | 无 | Tier 1：粘贴数据 + doh.py + Skill 静态分析 |
| **Phase 1** | LLM Key | Hermes 完整推理：创意、序列、EQS 报告 |
| **Phase 2** | + RESEND_API_KEY | 域认证、抑制同步、种子测试 |
| **Phase 3** | + HubSpot | CRM 分群、活动指标自动拉取 |

### 8.3 模型配置（后配时）

```bash
hermes setup          # 交互式选 provider + 填 Key
hermes model          # 选具体模型

# 或直接写入
hermes config set model.provider openrouter
hermes config set model.default anthropic/claude-sonnet-4
```

---

## 9. 记忆与协议层

### 9.1 目录职责

| 路径 | 写入者 | 内容 |
|------|--------|------|
| `memory/hot-cache.md` | 各 Skill promote | 会话热缓存（≤80 行） |
| `memory/open-loops.md` | 各 Skill | 未决事项 |
| `memory/consent/` | **consent-registry 唯一** | 同意/抑制 SSOT |
| `memory/consent/candidates.md` | 其他 Skill 投递 | 待 reconcile 候选 |
| `memory/claims/claims-ledger.md` | offer-claims-registry | D1 声明台账 |
| `memory/audits/email/` | **email-quality-auditor 唯一** | EQS 审计工件 |

### 9.2 审计工件示例

```markdown
---
class: auditor-output
framework: SEND
goal: promotional
status: FIX
cap_applied: false
raw_overall_score: 76
final_overall_score: 76
---

# 邮件质量审计 · 促销目标

| 维度 | 分数 | 健康 | 下一步 |
|------|------|------|--------|
| S 送达 | 72 | 中等 | 修复 DMARC p=none → quarantine |
| E 互动 | 68 | 中等 | 主题行 A/B 测试 |
| N 培育 | 80 | 良好 | — |
| D 转化 | 78 | 良好 | — |

**EQS: 76 · FIX · 可修复后发送**
```

### 9.3 健康标签对照

| 分数区间 | 健康标签 | 建议动作 |
|----------|----------|----------|
| 90–100 | 优秀 | SHIP |
| 75–89 | 良好 | SHIP 或 FIX（视否决项） |
| 60–74 | 中等 | FIX |
| 40–59 | 偏低 | FIX，暂缓发送 |
| 0–39 | 差 | BLOCK |
| 2+ 否决 | 阻断 | BLOCK，禁止发送 |

---

## 10. 实施阶段

### Phase 0：脚手架（0 Key，1 天）

- [ ] 初始化 `email_demo/` 目录结构
- [ ] 复制 `references/send-benchmark.md`、`auditor-runbook.md`、`skill-contract.md`
- [ ] 复制 `scripts/connectors/doh.py`、`_http.py`（及可选 `resend.py`）
- [ ] 创建 `hermes/config.yaml.example`、`.env.example`、`install.sh`
- [ ] 初始化 `memory/` 脚手架
- [ ] 编写 `AGENTS.md`、`README.md`

### Phase 1：P0 技能 + 路由（1–2 天）

- [ ] 编写 `skills/email-router/SKILL.md`
- [ ] 安装/移植 `email-quality-auditor`
- [ ] 安装/移植 `consent-registry`
- [ ] 安装/移植 `deliverability-qa`
- [ ] 配置 `~/.hermes/config.yaml` 指向项目 `skills/`
- [ ] 验证 Tier 1：粘贴 ESP 导出 → EQS 报告

### Phase 2：接入 LLM Key（后配，0.5 天）

- [ ] `hermes setup` + `hermes model`
- [ ] 端到端对话测试：`/email-router 审计促销邮件`
- [ ] 验证 Handoff Summary 与 memory 写入

### Phase 3：MCP 接线（后配 ESP Key，1 天）

- [ ] 启用 Resend MCP（`enabled: true` + RESEND_API_KEY）
- [ ] `/reload-mcp` 验证连通
- [ ] 端到端：doh.py → resend.domains → consent → EQS
- [ ] （可选）HubSpot MCP 接线

### Phase 4：扩展技能（按需）

- [ ] P1：`list-segment-builder`、`email-creative-builder`、`email-sequence-designer`
- [ ] P2：Engage / Nurture / Deliver 其余 9 技能
- [ ] （可选）Cursor 双栈：`.cursor/skills/` symlink → `skills/`

---

## 11. 典型工作流

### 11.1 发送前 EQS 审计

```
用户: /email-router 审计明天要发的促销广播，域名 mybrand.com

Agent 执行:
1. email-router → phase=deliver → email-quality-auditor
2. 确认 goal=promotional
3. Tier 1: python3 scripts/connectors/doh.py auth mybrand.com
4. Tier 2: MCP resend.domains（若 Key 已配）
5. 读 memory/consent/ → S2 检查
6. 读 memory/claims/claims-ledger.md → D1 检查
7. 用户粘贴 ESP 活动 CSV → E/N/D 评分
8. 计算 EQS + S1/S2/N1/D1 否决
9. 输出 SHIP/FIX/BLOCK + 写入 memory/audits/email/
10. Handoff → deliverability-qa（FIX）或 send-experiment-designer（SHIP）
```

### 11.2 列表分群 + 同意登记

```
用户: /consent-registry 登记这批 checkout 导入的 opt-in 记录

Agent 执行:
1. 读 candidates.md 或用户粘贴导入
2. GDPR lawful-basis gate
3. 写入 memory/consent/<subject>.md
4. Handoff → list-segment-builder（应用抑制分群）
```

### 11.3 送达率前置检查

```
用户: /deliverability-qa mybrand.com

Agent 执行:
1. doh.py auth mybrand.com → SPF/DKIM/DMARC 记录
2. 要求 DMARC RUA 报告（无则 NEEDS_INPUT）
3. 要求 inbox-placement 测试结果（无则 NEEDS_INPUT）
4. 输出 S 维度预检 + S1 风险标记
5. Handoff → list-hygiene-monitor 或 email-quality-auditor
```

---

## 12. 验证清单

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 技能可发现 | `hermes skills browse --tag email` | ≥ 5 个邮件技能 |
| Tier 1 无 Key | 粘贴 ESP CSV + doh.py | 产出 EQS 或 S 预检报告 |
| Golden math | S=80,E=75,N=70,D=78, promo | EQS = 76 |
| 否决封顶 | S1 触发 | min(76, 60) = 60 |
| 双否决 | S1 + S2 同时触发 | status = BLOCKED |
| MCP 连通 | `/reload-mcp` + resend.domains | 返回域状态 JSON |
| 记忆持久 | 审计后检查 | `memory/audits/email/` 有工件 |
| consent SSOT | 登记 opt-in 后 | `memory/consent/` 有记录 |
| dry-run 安全 | resend.py send 无 --live | 无实际发送 |

---

## 13. 风险与约束

| 风险 | 缓解 |
|------|------|
| standalone 技能缺 references | 项目内复制 `references/`，Skill 内写 raw.githubusercontent fallback |
| Hermes 无 Artifact Gate | 审计工件格式靠 Skill Instructions 约束，无机器校验 |
| MCP Key 泄露 | Key 只放 `~/.hermes/.env`，不进 git |
| 误发邮件 | mutating 默认 dry-run；MCP exclude broadcast-send |
| 合规误判 | 标注「风险指引，非法律意见」 |
| SEND 框架较新 | 分数带 provisional 标记，待 ~30 次真实审计校准 |

---

## 14. 待确认事项

实施 Phase 1 前需确认：

| 项 | 选项 | 影响 |
|----|------|------|
| **ESP 首选** | Resend / HubSpot / 纯手动导出 | MCP 优先级与 install.sh 默认配置 |
| **LLM 提供商** | OpenRouter / Anthropic / 国内 OpenAI-compatible | `.env.example` 默认值与 config 模板 |
| **技能来源** | 本地维护 vs skills.sh 拉取 vs 混合 | 更新策略与 frontmatter 控制权 |
| **Cursor 双栈** | 是 / 否 | 是否创建 `.cursor/skills/` symlink |

---

## 附录 A：upstream 参考链接

| 资源 | URL |
|------|-----|
| SEND Benchmark | https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/references/send-benchmark.md |
| Auditor Runbook | https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/references/auditor-runbook.md |
| Agent Compatibility | https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/docs/agent-compatibility.md |
| MCP Catalog | https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/docs/mcp-catalog.json |
| Hermes Configuration | https://hermes-agent.nousresearch.com/docs/user-guide/configuration |
| Hermes MCP Reference | https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference |

## 附录 B：与 Cursor 双栈兼容（可选）

同一项目可同时服务 Hermes 与 Cursor：

```bash
mkdir -p .cursor
ln -s ../skills .cursor/skills
```

| 运行时 | 技能路径 | 配置文件 |
|--------|----------|----------|
| Hermes | `skills/` via `external_dirs` | `~/.hermes/config.yaml` |
| Cursor | `.cursor/skills/` | `.cursor/mcp.json` |

---

*文档版本：v1.0 · 2026-07-08*
