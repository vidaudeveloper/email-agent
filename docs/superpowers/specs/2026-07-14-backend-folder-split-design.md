# Backend 目录拆分与可部署交付设计

**日期：** 2026-07-14  
**状态：** 已审阅（对话确认）  
**产品：** Vidau Mobile / Cloud Agent  
**范围：** 将 worktree 中的 `cloud_agent` 迁入主仓根目录 `backend/`，使后端同事可单独拷贝该目录部署到服务器  
**非目标：** Link Gateway、独立 backend git 仓库、Firecracker 生产沙箱默认化、Flutter API 契约变更

**关联文档：**

- [Cloud Agent 产品设计](./2026-07-11-vidau-cloud-agent-design.md)
- [Mobile Link 一期](./2026-07-10-vidau-mobile-link-phase1-design.md)（并行产品轨，本次不搬）

---

## 1. 目标

### 1.1 产品 / 工程目标

主仓根目录提供自包含的 `backend/`：包含 Cloud Agent（FastAPI）源码、静态资产、脱敏样例数据、Docker 与生产启动脚本。后端同事拿到 `backend` 文件夹即可按 README 部署，无需理解 Flutter 或 worktree 结构。

### 1.2 成功标准

1. 主仓存在唯一后端源码树：`backend/`。
2. 仅拷贝 `backend/`，按 README 可启动，且 `GET /health` 通过。
3. 仓库不含真实密钥、真实会话附件、`.venv`。
4. Flutter ↔ Cloud Agent 的 HTTP/WS 契约不变（仍默认 `:8787`）。
5. 文档入口路径从 `cloud_agent/` / `.worktrees/.../cloud_agent` 更新为 `backend/`。

---

## 2. 已锁定决策

| 议题 | 决策 |
|---|---|
| 搬迁范围 | **仅** worktree 的 `cloud_agent`（Cloud Agent）；不含 Link Gateway / `mobile_agent_service` |
| 交付形态 | 搬家 + **生产可运行包**：Dockerfile、docker-compose、`.env.example`、`run_prod.sh` |
| 目录形态 | **扁平** `backend/`（`app/` 直接在其下），不保留 `backend/cloud_agent/` 嵌套 |
| 源路径 | 从 `.worktrees/cloud-agent-p0/cloud_agent` **移动**到主仓 `backend/` |
| 数据策略 | **脱敏样例**：空会话列表 / 示例 `installed`；不含真实密钥与运行态库 |
| Worktree | 搬走后删除 worktree 内 `cloud_agent/` 副本；不强制删除整个 worktree（Flutter 改动可仍留在分支） |
| Link Gateway | 并行产品轨，本次不动；仍独立于 `mobile_agent_service` |

---

## 3. 目标目录结构

```text
mobile_agent/
  backend/                         # 可单独拷贝部署
    app/                           # FastAPI 应用（原 cloud_agent/app）
    data/
      catalog.json                 # 静态 Catalog
      skills/                      # 静态 Skill 包
      installed.json               # 脱敏样例（示例已装 Expert）
      cloud_sessions.json          # 空列表样例 []
      account_auth.json            # 空/占位样例（无真实 token）
      # 不纳入 git：sessions.db、sessions/、sandboxes/、openvidau.env
    tests/
    scripts/
      run_dev.sh                   # 开发：可 --reload
      run_prod.sh                  # 生产：无 --reload，0.0.0.0
    Dockerfile
    docker-compose.yml
    .env.example
    .gitignore
    requirements.txt
    README.md                      # 后端同事部署入口
  lib/ ...                         # Flutter 客户端（不动契约）
  docs/ ...
```

### 3.1 纳入 / 排除

| 纳入 | 排除 |
|---|---|
| `app/`、`tests/`、`scripts/`、`requirements.txt` | `.venv/`、`__pycache__/`、`.pytest_cache/` |
| `data/catalog.json`、`data/skills/` | `data/sessions.db`、`data/sessions/`、`data/sandboxes/` |
| 脱敏样例 JSON（见上） | `data/openvidau.env`、真实 API key、真实 SSO 会话 |
| Docker / compose / `.env.example` / 生产脚本 | 本机调试用临时文件 |

### 3.2 脱敏样例约定

- `cloud_sessions.json`：`[]` 或等价空结构，与现有 store 读取兼容。
- `installed.json`：可含演示用 expert id 列表，**不含**用户密钥。
- `account_auth.json`：空对象或空映射；部署后由 SSO / 运维写入真实态（写在 volume，不回写仓库）。

---

## 4. Docker 与运行配置

### 4.1 容器

- 基础镜像：Python 3.11-slim。
- 安装 `requirements.txt`；工作目录为 `/app`（或等价），`PYTHONPATH` 指向服务根。
- `CMD` 调用生产启动（uvicorn，无 `--reload`），监听 `0.0.0.0:8787`。
- 健康检查：`GET /health`。

### 4.2 Compose

- 映射宿主机端口 `8787:8787`。
- 运行态 volume：会话库、附件目录、沙箱目录、以及服务器侧写入的 env/凭证文件（如 `openvidau.env`）。
- 静态 `catalog.json` / `skills/` 打入镜像（或只读挂载）；不以开发机真实会话为依赖。

### 4.3 环境变量（`.env.example`）

| 变量 | 生产建议 | 说明 |
|---|---|---|
| `CLOUD_AGENT_PUBLIC_BASE_URL` | 对外 HTTPS 基址 | 附件 URL 绝对化 |
| `CLOUD_AGENT_ALLOW_DEV_TOKEN` | `false` | 禁用 `dev-local-token` |
| `CLOUD_AGENT_CORS_ORIGINS` | 实际来源 | 禁用通配 `*`（生产） |
| `CLOUD_AGENT_OPENVIDAU_BASE_URL` | 现网 SSO | 默认可与现配置一致 |
| `CLOUD_AGENT_OPENVIDAU_CLIENT_APP` | 现网 client | 如 `vidau-mobile` / `vidau-desktop` |
| `CLOUD_AGENT_LLM_*` | 服务器配置或依赖 SSO 写入 | **不进 git** |
| `CLOUD_AGENT_SANDBOX_PROVIDER` | `local`（现阶段） | Firecracker 另议 |
| `CLOUD_AGENT_MCP_MODE` | `auto` / `real` | 生产不长期 `mock` |

密钥仅存在于服务器 `.env` 或密钥管理系统。

### 4.4 启动入口（README）

```bash
cd backend
cp .env.example .env   # 填写密钥与 PUBLIC_BASE_URL
docker compose up -d
# 或：python3.11 -m venv .venv && source .venv/bin/activate
#     pip install -r requirements.txt && ./scripts/run_prod.sh
curl http://localhost:8787/health
```

---

## 5. 搬迁与 Worktree 流程

1. 在主仓创建 `backend/`，从 `.worktrees/cloud-agent-p0/cloud_agent` 复制/移动纳入清单中的文件。
2. 生成脱敏样例 data、`.gitignore`、`.env.example`、`Dockerfile`、`docker-compose.yml`、`scripts/run_prod.sh`，并改写 `backend/README.md` 为部署文档。
3. 删除 worktree 内 `cloud_agent/`，避免双份后端源码。
4. 更新主仓根 `README.md` 与 Cloud Agent 相关 specs/plans 中的启动路径为 `backend/`。
5. 不强制合并 `feature/cloud-agent-p0` 的 Flutter 改动；后端交付与客户端分支解耦。

本地联调默认：主仓 `backend/` + Flutter（主仓或 worktree）通过 `CLOUD_HOST` / `CLOUD_AGENT_PUBLIC_BASE_URL` 指向同一服务。

---

## 6. 文档更新范围

| 位置 | 改动 |
|---|---|
| `backend/README.md` | 部署与环境变量权威入口 |
| 根 `README.md` | 增加 Cloud Agent：`cd backend && ...` |
| `docs/superpowers/specs/2026-07-11-vidau-cloud-agent-design.md` 等 | 路径 `cloud_agent/` → `backend/`；去掉 worktree 专用启动示例 |
| 相关 plans | 纠正入口路径；不重写已完成任务的大段历史正文 |

---

## 7. 风险与明确不做

| 风险 | 缓解 |
|---|---|
| 误提交密钥 / 会话附件 | `backend/.gitignore` + 搬迁时显式排除清单 |
| 文档仍指向 worktree | 同步改 specs/plans 入口；根 README 写新路径 |
| 双份源码漂移 | worktree 删除 `cloud_agent/` |

**本轮明确不做：**

- 拆独立 backend git 仓库 / submodule
- 迁入 Link Gateway
- K8s / 多副本编排
- 默认启用 Firecracker
- 变更 Flutter API / WS 协议

---

## 8. 验收清单

- [ ] 主仓 `backend/` 可独立 `docker compose up` 或 `run_prod.sh` 启动
- [ ] `/health` 返回成功且含预期字段（如 mcp/llm 状态）
- [ ] git 状态中无 `.venv`、无 `openvidau.env`、无真实 `sessions/` 附件
- [ ] worktree 中不再存在 `cloud_agent/` 源码树
- [ ] 文档入口已指向 `backend/`
