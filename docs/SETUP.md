# Setup — 独立 Hermes（本仓库）

> 使用项目内 `.hermes/`，**不读写** `~/.hermes`（除非你主动跑 `install-skills.mjs`）。  
> 一键总览见根目录 [SETUP.md](../SETUP.md)。

## 1. 安装 Hermes CLI

[Hermes Agent 文档](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)

## 2. 初始化本项目环境

```bash
cd /path/to/email-agent   # 本仓库根目录
bash hermes/install.sh
```

会创建：

| 路径 | 说明 |
|------|------|
| `.hermes/.env` | **API Key / EMAIL_* 位置**（模板：`hermes/.env.example`） |
| `.hermes/config.yaml` | 模型、技能路径、MCP（`__PROJECT_ROOT__` 已替换） |

`hermes/run.sh` 还会导出 `EMAIL_AGENT_ROOT`（skills 发信命令依赖它）。

## 3. 配置 Key

编辑 **`.hermes/.env`**：

```bash
VIDAU_API_KEY=tw-你的密钥
OPENAI_BASE_URL=https://open.vidau.ai/v1
OPENAI_API_KEY=tw-你的密钥

# 发信二选一（send_mail.py 优先 SMTP）
# EMAIL_ADDRESS=… / EMAIL_PASSWORD=… / EMAIL_SMTP_HOST=…   # 或依赖桌面 Messaging Email
# RESEND_API_KEY=re_…   # 无个人 SMTP 时
```

桌面已配置 **Messaging → Email** 时，`user_smtp.py` / `send_mail.py` 会自动读 `%LOCALAPPDATA%/vidau/.env`（Windows），无需再抄一份。

## 4. 启动

```bash
bash hermes/run.sh chat
```

## 5. 发信验证

```bash
export EMAIL_AGENT_ROOT="$(pwd)"
set -a && source .hermes/.env && set +a
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" status
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/doh.py" auth mail.vidau.ai
# 仅走 Resend 时：
# python3 "$EMAIL_AGENT_ROOT/scripts/connectors/resend.py" domains
bash scripts/verify-deliver-flow.sh --domain mail.vidau.ai
```

真发前：consent → EQS **SHIP** → `send_mail.py … --live`。

## 6. 可选 Resend MCP

```bash
bash hermes/enable-resend.sh
bash hermes/run.sh chat
# /reload-mcp
```

## 环境变量

| 变量 | 值 |
|------|-----|
| `EMAIL_AGENT_ROOT` | 仓库根（`run.sh` 设置） |
| `HERMES_HOME` | `$EMAIL_AGENT_ROOT/.hermes` |
| 密钥 / EMAIL_* | `.hermes/.env` 或 VidAU `%LOCALAPPDATA%/vidau/.env` |
