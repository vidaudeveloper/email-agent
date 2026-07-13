# Setup — email_demo 独立 Hermes

> 使用项目内 `.hermes/`，**不读写** `~/.hermes`，与其他项目完全隔离。

## 1. 安装 Hermes CLI

[Hermes Agent 文档](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)

## 2. 初始化本项目环境

```bash
cd /Users/kean/Desktop/DemoFile/email_demo
bash hermes/install.sh
```

会创建：

| 路径 | 说明 |
|------|------|
| `email_demo/.hermes/.env` | **API Key 唯一位置** |
| `email_demo/.hermes/config.yaml` | 模型、技能路径、MCP |

## 3. 配置 Vidau API Key

编辑 **`email_demo/.hermes/.env`**：

```bash
VIDAU_API_KEY=tw-你的密钥
OPENAI_BASE_URL=https://open.vidau.ai/v1
OPENAI_API_KEY=tw-你的密钥
```

默认模型在 `.hermes/config.yaml` 中为 `gpt-4o-mini`（可在 [控制台](https://open.vidau.ai/zh/dashboard/models) 换 id）。

## 4. 启动（独立运行）

```bash
cd /Users/kean/Desktop/DemoFile/email_demo

# 交互式
bash hermes/run.sh chat

# 单次任务
bash hermes/run.sh chat "/email-router audit my promotional email"
bash hermes/run.sh chat "/email-quality-auditor promotional"
```

`run.sh` 会自动设置 `HERMES_HOME=email_demo/.hermes`，不会碰到全局 `~/.hermes`。

## 5. 验证

```bash
# Tier 1 — 无需 LLM Key
python3 scripts/connectors/doh.py auth example.com

# Tier 2 — 有 Vidau Key 后
export HERMES_HOME="$(pwd)/.hermes"
set -a && source .hermes/.env && set +a
curl -s https://open.vidau.ai/v1/models -H "Authorization: Bearer $VIDAU_API_KEY" | head

bash hermes/run.sh skills browse --tag email
```

## 6. 可选 Resend MCP

在 `.hermes/.env` 添加 `RESEND_API_KEY`，然后：

```bash
bash hermes/enable-resend.sh
bash hermes/run.sh chat
# 在 TUI：
/reload-mcp
```

真发用 `scripts/connectors/resend.py`（默认 dry-run，`--live` 仅在 EQS **SHIP** 后）。不要用 SMTP / `smtplib`。

## 7. 自然语言 vs 斜杠命令

Hermes **不会**在自然语言时自动注入 skill；只有 `/email-router` 这类斜杠命令会硬注入。本项目用三层补强：

1. `bash hermes/run.sh chat` **默认** `--skills email-router`（预加载路由）
2. `hooks.pre_llm_call`：邮件相关话术注入「禁止 SMTP / 走 resend.py」
3. `hooks.pre_tool_call`：拦截 `smtplib` / 裸 SMTP

仍建议优先用斜杠命令。改完配置后请 **退出旧会话**，再 `bash hermes/run.sh chat`（不要 `--continue` 旧 session）。

## 环境变量说明

| 变量 | 值 |
|------|-----|
| `HERMES_HOME` | `email_demo/.hermes`（由 `run.sh` 设置） |
| 密钥文件 | `email_demo/.hermes/.env` |
| 身份 / 硬规则 | `email_demo/.hermes/SOUL.md`（模板：`hermes/SOUL.md.template`） |
