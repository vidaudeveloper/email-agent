# Vidau Cloud Agent (backend)

FastAPI 服务：手机 **云端执行**（Catalog / Session / WS / MCP / SSO）。  
本目录可单独拷贝到服务器部署；**不含** Mobile Link Gateway。

## 快速部署（Docker，推荐）

```bash
cd backend
cp .env.example .env
# 编辑 .env：填写 PUBLIC_BASE_URL、CORS、LLM/SSO 相关项
docker compose up -d --build
curl http://localhost:8787/health
```

`./data` 挂载进容器：内含 `catalog.json`、`skills/`、脱敏样例；运行时会话库与密钥（如 `openvidau.env`）写在同一目录，**不要提交真实密钥**。

## 无 Docker（venv）

需要 Python **3.11+**。

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
./scripts/run_prod.sh
```

开发热重载：

```bash
./scripts/run_dev.sh
```

## 环境变量

| 变量 | 生产建议 | 说明 |
|------|----------|------|
| `CLOUD_AGENT_PUBLIC_BASE_URL` | 对外 HTTPS 基址 | 附件 URL 绝对化 |
| `CLOUD_AGENT_ALLOW_DEV_TOKEN` | `false` | 禁用 `dev-local-token` |
| `CLOUD_AGENT_CORS_ORIGINS` | 实际 App/域名 | 勿用 `*` |
| `CLOUD_AGENT_OPENVIDAU_BASE_URL` | `https://open.vidau.ai` | SSO |
| `CLOUD_AGENT_OPENVIDAU_CLIENT_APP` | `vidau-mobile` 等 | SSO client |
| `CLOUD_AGENT_LLM_*` | 服务器配置或依赖 SSO | **勿提交到 git** |
| `CLOUD_AGENT_SANDBOX_PROVIDER` | `local` | 现阶段 |
| `CLOUD_AGENT_MCP_MODE` | `auto` / `real` | 生产勿长期 `mock` |

前缀均为 `CLOUD_AGENT_`（见 `app/config.py`）。

## 鉴权

- 生产：OpenVidAU SSO（`POST /v1/auth/login-ticket` → poll）；Key 只留在服务器 `data/openvidau.env`
- 本地调试：可将 `CLOUD_AGENT_ALLOW_DEV_TOKEN=true`，使用 `Authorization: Bearer dev-local-token`

## 健康检查

```bash
curl http://localhost:8787/health
```

期望 JSON 含 `mcp_mode`、`llm_configured` 等字段。

## 测试

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

## 目录说明

```text
backend/
  app/                 # FastAPI
  data/                # catalog、skills、样例与运行态
  scripts/run_dev.sh   # 开发
  scripts/run_prod.sh  # 生产（无 --reload）
  Dockerfile
  docker-compose.yml
  .env.example
  requirements.txt
```

## 非本目录范围

- Flutter 客户端：仓库根目录
- Link Gateway（连电脑）：独立服务 `mobile_agent_service`，不在此包
