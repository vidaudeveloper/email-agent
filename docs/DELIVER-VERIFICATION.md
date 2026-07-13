# Deliver 阶段验证指南（客户版）

> **Deliver 在 SEND 框架里 = 发送决策 + 实验 + 发后监测**，不是「一键群发」。  
> 真正点发送可在 ESP 控制台操作，或通过 Resend（Tier 2，默认 dry-run）。

## Deliver 四个 Skill（已全部安装）

| Skill | 斜杠命令 | 客户价值 |
|-------|----------|----------|
| ⛩ Email Quality Auditor | `/email-quality-auditor` | 发送前 **SHIP / FIX / BLOCK** |
| Send Experiment Designer | `/send-experiment-designer` | A/B、发送时间、hold-out 实验 |
| Inbox Placement Monitor | `/inbox-placement-monitor` | 发后进收件箱还是垃圾箱 |
| Cold Outbound Sequencer | `/cold-outbound-sequencer` | B2B 冷邮件多步序列 |

---

## 一键自动检查（推荐先做）

```bash
cd /Users/kean/Desktop/DemoFile/email_demo
bash scripts/verify-deliver-flow.sh --domain yourdomain.com
```

**通过标准**：最后一行 `Result: READY`，无 `[FAIL]`。

---

## 路径 A：Tier 1（无需 Resend，最常见）

客户在 ESP（Klaviyo / Mailchimp / 企业邮箱）里手动发送。

### 1. 发送前放行

```
bash hermes/run.sh chat
```

```
/email-quality-auditor promotional
域名：yourdomain.com
目标：夏季清仓广播
邮件 HTML：[粘贴正文]
consent：已在 /consent-registry 登记
claims：8 折已在 /offer-claims-registry 登记
```

| 裁决 | 含义 | 客户动作 |
|------|------|----------|
| **SHIP** | 可发 | 去 ESP 创建活动并发送 |
| **FIX** | 有问题但无红线 | 按清单修完再审 |
| **BLOCK** | 触红线 | 禁止发送，先修认证/同意/声明 |

### 2. 实验设计（可选）

```
/send-experiment-designer 设计主题行 A/B：A="夏季清仓 8 折" B="最后 48 小时"，列表 10000
```

### 3. ESP 手动发送

在 Klaviyo / Resend 控制台创建活动 → 发送。

### 4. 发后监测

```
/inbox-placement-monitor 粘贴 seed 测试结果：Gmail inbox，Outlook promotions...
/performance-analyzer 粘贴 ESP 活动 CSV
/roi-calculator 计算 revenue-per-send
```

---

## 路径 B：Tier 2（Resend 自动化）

### 1. 配置 Key

编辑 `email_demo/.hermes/.env`：

```bash
RESEND_API_KEY=re_你的密钥
```

### 2. 验证域与连接器

```bash
python3 scripts/connectors/resend.py domains
bash scripts/verify-deliver-flow.sh
```

应看到 `resend.py domains (read-only)` 为 PASS。

### 3. 启用 Resend MCP（可选，供 Hermes 对话拉数据）

```bash
bash hermes/enable-resend.sh
bash hermes/run.sh chat
# 在 TUI 输入：
/reload-mcp
```

### 4. Seed 测试（配合 inbox-placement-monitor）

**先 dry-run（不真发）：**

```bash
python3 scripts/connectors/resend.py seed \
  --from "you@verified-domain.com" \
  --to "your-gmail@gmail.com" \
  --subject "[placement test] 夏季清仓" \
  --html memory/deliver-verify-sample.html
```

**确认预览无误后再真发：**

```bash
python3 scripts/connectors/resend.py seed \
  --from "you@verified-domain.com" \
  --to "your-gmail@gmail.com,your-outlook@outlook.com" \
  --subject "[placement test] 夏季清仓" \
  --html memory/deliver-verify-sample.html \
  --live
```

然后到各 seed 邮箱查看：inbox / promotions / spam。

```
/inbox-placement-monitor 根据 seed 结果分析落点
```

### 5. 单封测试发送

```bash
# dry-run
python3 scripts/connectors/resend.py send \
  --from "you@verified-domain.com" \
  --to "test@example.com" \
  --subject "测试" \
  --html memory/deliver-verify-sample.html

# 真发（仅 SHIP 之后）
python3 scripts/connectors/resend.py send ... --live
```

### 6. 广播（促销群发）

> MCP 默认排除 `broadcast-send`；用 CLI 时需团队明确授权。

```bash
python3 scripts/connectors/resend.py broadcast-create \
  --segment <SEGMENT_ID> \
  --from "you@verified-domain.com" \
  --subject "夏季清仓 8 折" \
  --html campaign.html

python3 scripts/connectors/resend.py broadcast-send <BROADCAST_ID> \
  --at "2026-07-10T02:00:00Z" \
  --live
```

---

## 完整 Deliver 链路（促销场景）

```
deliverability-qa          → S1 认证预检
email-creative-builder     → 写邮件
offer-claims-registry      → 登记 8 折声明
consent-registry           → 确认 opt-in
email-quality-auditor      → SHIP / FIX / BLOCK  ← Deliver 核心
[ESP 或 resend.py --live]  → 真发
inbox-placement-monitor    → 发后落点
performance-analyzer       → 效果复盘
```

Hermes 一条命令走规划：

```
/email-router promotional — 夏季清仓 8 折，走完 deliverability → creative → auditor，SHIP 后说明如何用 resend seed 测试
```

---

## 安全说明（与参考项目一致）

| 规则 | 说明 |
|------|------|
| 默认 dry-run | `resend.py` 不带 `--live` 不会真发 |
| 先审计再发 | 建议 `email-quality-auditor` SHIP 后再 `--live` |
| consent SSOT | Resend 发信不自动创建 opt-in，须先 `/consent-registry` |
| MCP 广播 | 默认 exclude `broadcast-send`，防误触群发 |

---

## 验收清单

- [ ] `bash scripts/verify-deliver-flow.sh` → READY
- [ ] `/email-quality-auditor` → 有 SHIP/FIX/BLOCK
- [ ] `/send-experiment-designer` → 有实验方案
- [ ] `/inbox-placement-monitor` → 说明需要的数据
- [ ] （可选）`resend.py domains` → 返回域列表
- [ ] （可选）`resend.py seed ... --live` → seed 邮箱收到测试信
