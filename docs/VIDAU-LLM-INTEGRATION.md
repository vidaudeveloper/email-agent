# Vidau OPEN LLM 接入 — email_demo 独立环境

> 平台：[open.vidau.ai](https://open.vidau.ai/zh/docs/api参考文档)  
> 本项目使用 **`email_demo/.hermes/`**，不共用 `~/.hermes`。

---

## API 概要

| 项 | 值 |
|----|-----|
| Base URL | `https://open.vidau.ai/v1` |
| 认证 | `Authorization: Bearer tw-...` |
| 协议 | OpenAI 兼容（chat/completions、models） |

---

## 配置位置（仅两处，都在项目内）

| 文件 | 内容 |
|------|------|
| **`email_demo/.hermes/.env`** | `VIDAU_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_API_KEY` |
| **`email_demo/.hermes/config.yaml`** | `model.default`、`skills.external_dirs`、MCP |

初始化：

```bash
cd /Users/kean/Desktop/DemoFile/email_demo
bash hermes/install.sh
```

编辑 `.hermes/.env`：

```bash
VIDAU_API_KEY=tw-你的密钥
OPENAI_BASE_URL=https://open.vidau.ai/v1
OPENAI_API_KEY=tw-你的密钥
```

---

## 默认模型推荐

| 场景 | 模型 id | 说明 |
|------|---------|------|
| 默认 | `gpt-4o-mini` | 路由、创意、日常 |
| EQS 审计 | `gpt-4o` 或控制台 Claude Sonnet | 发送前 go/no-go |
| 长 ESP 导出 | 控制台中长上下文 Gemini/Claude | 粘贴大 CSV |

在 [控制台模型列表](https://open.vidau.ai/zh/dashboard/models) 确认 exact id 后，改 `.hermes/config.yaml` 的 `model.default`。

---

## 启动

```bash
bash hermes/run.sh chat
bash hermes/run.sh chat "/email-quality-auditor promotional"
```

`run.sh` 设置 `HERMES_HOME=email_demo/.hermes`，与全局 Hermes 及其他项目隔离。

---

## 验证

```bash
export HERMES_HOME="$(pwd)/.hermes"
set -a && source .hermes/.env && set +a
curl -s https://open.vidau.ai/v1/models -H "Authorization: Bearer $VIDAU_API_KEY" | head
python3 scripts/connectors/doh.py auth example.com
```

---

## 可选 Resend MCP

`.hermes/.env` 加 `RESEND_API_KEY`，`.hermes/config.yaml` 设 `mcp_servers.resend.enabled: true`，chat 内 `/reload-mcp`。

*详见 [SETUP.md](SETUP.md)*
