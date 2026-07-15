# Email Agent (Hermes Skills) — One-Click Setup

仓库：https://github.com/vidaudeveloper/email-agent  
目标：通过 SEND skills + `scripts/connectors/send_mail.py` **安全发信**（默认 dry-run，`--live` 才真发）。

发信优先级：

1. **VidAU Messaging Email（个人 SMTP）** — 必须先配置；未配置时 skill / `send_mail.py` 会提示去桌面 Messaging → Email 填写并保存
2. **Resend（可选）** — 仅当用户明确要求时用 `--transport resend` + `RESEND_API_KEY`

> 不要用 `raw.githubusercontent.com` 拉 skill（易 429）。优先 shallow clone + 本地安装。

---

## 1. Clone（推荐，零 raw CDN）

```bash
git clone --depth 1 https://github.com/vidaudeveloper/email-agent.git
cd email-agent
```

可选：把 skills 拷到全局 Hermes：

```bash
node scripts/install-skills.mjs --force
```

脚本读取 `_manifest.yaml`（**不要手写 skill 名**），安装到 `~/.hermes/skills/vidau-email/`，并写入 `EMAIL_AGENT_ROOT`。

**Fallback（无本地副本但有 git）：**

```bash
git clone --depth 1 https://github.com/vidaudeveloper/email-agent.git /tmp/email-agent
node /tmp/email-agent/scripts/install-skills.mjs --remote --force
```

**Fallback（无 git）：** 用 GitHub Contents API 读 `_manifest.yaml`，再：

```bash
node scripts/install-skills.mjs --from-github --force
```

安装后核对：已装 skill id 集合 == `_manifest.yaml` 里每个 `skills[].id`。

---

## 2. 独立 Hermes 运行时（发信推荐路径）

```bash
bash hermes/install.sh
```

编辑 **`.hermes/.env`**（从 `hermes/.env.example` 复制）：

```bash
VIDAU_API_KEY=tw-你的密钥
OPENAI_BASE_URL=https://open.vidau.ai/v1
OPENAI_API_KEY=tw-你的密钥

# 二选一（send_mail.py 优先用 SMTP）
# A) 个人邮箱 — 也可不写，会自动读 %LOCALAPPDATA%/vidau/.env（桌面 Messaging → Email）
# EMAIL_ADDRESS=you@gmail.com
# EMAIL_PASSWORD=应用专用密码
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587

# B) Resend（无个人 SMTP 时）
# RESEND_API_KEY=re_你的密钥
```

`hermes/run.sh` 会自动导出：

- `HERMES_HOME=$REPO/.hermes`
- `EMAIL_AGENT_ROOT=$REPO`（skills 里所有发信命令依赖此变量）

启动：

```bash
bash hermes/run.sh chat
```

可选 Resend MCP：

```bash
bash hermes/enable-resend.sh
# 在 TUI：/reload-mcp
```

---

## 3. 发信工作流（必须遵守）

1. 收件人已在 `memory/consent/` 登记（`/consent-registry`）
2. `/email-quality-auditor` 得到 **SHIP**（非 FIX/BLOCK）
3. 执行统一连接器（默认 **dry-run**）：

```bash
set -a && source .hermes/.env && set +a
export EMAIL_AGENT_ROOT="$(pwd)"

# 看将用哪条通道
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" status

python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" send \
  --to "recipient@real-domain.com" \
  --subject "主题" \
  --html path/to/build.html
# 确认 dry-run 输出无误且 EQS=SHIP 后，再加 --live
```

强制走某一通道：

```bash
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" send --transport smtp …   # 个人 SMTP
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" send --transport resend \
  --from "you@mail.vidau.ai" …
```

硬规则：

- **禁止** 临时拼 `smtplib` / 裸 SMTP / `himalaya`（须走 `send_mail.py` / `user_smtp.py` / `resend.py`）
- **禁止** 占位收件人 `*@example.com`
- 走 Resend 时发件域须已验证（如 `mail.vidau.ai`，不要用未验证的裸 `vidau.ai`）

---

## 4. 使配置生效

退出旧会话后重新：

```bash
bash hermes/run.sh chat
```

或在 TUI：`/reset` / `/new`，必要时 `/reload-mcp`。

---

## 5. 验证

```bash
# 个人 SMTP（桌面已配置 Messaging Email 即可）
python3 scripts/connectors/send_mail.py status
# 期望 preferred: "smtp"

# Tier 1 — 无需 Key
python3 scripts/connectors/doh.py auth mail.vidau.ai

# Tier 2 — 仅当走 Resend 时需 RESEND_API_KEY
set -a && source .hermes/.env && set +a
python3 scripts/connectors/resend.py domains
bash scripts/verify-deliver-flow.sh --domain mail.vidau.ai
```

---

## Quick test prompts

```
帮我写一封 Meta 智能投放推广邮件（只要文案，先不要发送）
对这封邮件做 EQS 审计，目标 promotional
我已在 Messaging 配好个人邮箱，收件人已在 consent 登记，可以 dry-run 发一封测试吗？
查一下当前发信通道（send_mail.py status）
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| skill 里路径指向 `/Users/kean/...` | 更新到最新 `main`；或跑 `python3 scripts/fix-skill-paths.py` |
| `preferred: none` / `needs_setup` | 按提示打开 VidAU → Messaging → Email 配置个人邮箱并保存后重试 |
| `RESEND_API_KEY` 未设置且无 SMTP | 二选一配置后重启 `run.sh` |
| dry-run 正常但 SMTP `--live` 失败 | 检查应用专用密码 / SMTP 主机端口；Gmail 需开启 2FA + App Password |
| dry-run 正常但 Resend `--live` 失败 | 检查发件域是否已 verified；看 `resend.py domains` |
| `EMAIL_AGENT_ROOT` 空 | 用 `bash hermes/run.sh`，或手动 `export EMAIL_AGENT_ROOT=$(pwd)` |
