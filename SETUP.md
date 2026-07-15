# Email Agent (Hermes Skills) — One-Click Setup

仓库：https://github.com/vidaudeveloper/email-agent  
目标：通过 SEND skills + `scripts/connectors/resend.py` **安全发信**（默认 dry-run，`--live` 才真发）。

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
RESEND_API_KEY=re_你的密钥
```

`hermes/run.sh` 会自动导出：

- `HERMES_HOME=$REPO/.hermes`
- `EMAIL_AGENT_ROOT=$REPO`（skills 里所有 `resend.py` 命令依赖此变量）

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
3. 执行连接器（默认 **dry-run**）：

```bash
set -a && source .hermes/.env && set +a
export EMAIL_AGENT_ROOT="$(pwd)"

python3 "$EMAIL_AGENT_ROOT/scripts/connectors/resend.py" domains

python3 "$EMAIL_AGENT_ROOT/scripts/connectors/resend.py" send \
  --from "you@mail.vidau.ai" \
  --to "recipient@example.com" \
  --subject "主题" \
  --html path/to/build.html
# 确认 dry-run 输出无误且 EQS=SHIP 后，再加 --live
```

硬规则：

- **禁止** `smtplib` / 裸 SMTP / `himalaya`
- **禁止** 占位收件人 `*@example.com`
- 发件域须已在 Resend 验证（如 `mail.vidau.ai`，不要用未验证的裸 `vidau.ai`）

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
# Tier 1 — 无需 Key
python3 scripts/connectors/doh.py auth mail.vidau.ai

# Tier 2 — 需 RESEND_API_KEY
set -a && source .hermes/.env && set +a
python3 scripts/connectors/resend.py domains
bash scripts/verify-deliver-flow.sh --domain mail.vidau.ai
# 期望末行 Result: READY
```

---

## Quick test prompts

```
帮我写一封 Meta 智能投放推广邮件（只要文案，先不要发送）
对这封邮件做 EQS 审计，目标 promotional
域名 mail.vidau.ai，收件人已在 consent 登记，可以 dry-run 发一封测试吗？
查一下 Resend 域名认证状态
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| skill 里路径指向 `/Users/kean/...` | 更新到最新 `main`；或跑 `python3 scripts/fix-skill-paths.py` |
| `RESEND_API_KEY` 未设置 | 写入 `.hermes/.env` 后重启 `run.sh` |
| dry-run 正常但 `--live` 失败 | 检查发件域是否在 Resend 已 verified；看 `resend.py domains` |
| `EMAIL_AGENT_ROOT` 空 | 用 `bash hermes/run.sh`，或手动 `export EMAIL_AGENT_ROOT=$(pwd)` |
