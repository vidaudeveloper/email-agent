# Backend Folder Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Cloud Agent from `.worktrees/cloud-agent-p0/cloud_agent` into main-repo `backend/` as a self-contained, Docker-deployable package with sanitized sample data.

**Architecture:** Flat `backend/` at repo root (no nested `cloud_agent/`). Copy source + static skills/catalog; replace runtime JSON with sanitized samples; add Dockerfile, compose, `.env.example`, `run_prod.sh`; remove worktree copy; update docs paths.

**Tech Stack:** FastAPI, uvicorn, Docker Compose, Python 3.11

**Spec:** `docs/superpowers/specs/2026-07-14-backend-folder-split-design.md`

---

## File map

| Path | Responsibility |
|---|---|
| `backend/app/` | FastAPI application (moved) |
| `backend/tests/` | Pytest suite (moved) |
| `backend/data/catalog.json` + `skills/` | Static assets (moved) |
| `backend/data/*.json` samples | Sanitized empty/demo state |
| `backend/scripts/run_dev.sh` | Dev server with `--reload` |
| `backend/scripts/run_prod.sh` | Prod server without reload |
| `backend/Dockerfile` | Production image |
| `backend/docker-compose.yml` | Port + runtime volumes |
| `backend/.env.example` | Required env template |
| `backend/.gitignore` | Exclude venv, sessions, secrets |
| `backend/README.md` | Deploy entry for backend teammates |
| Root `.gitignore` + `README.md` | Point at `backend/` |
| Cloud Agent specs/plans | Path `cloud_agent` → `backend` |

---

### Task 1: Copy source into `backend/` (exclude runtime)

**Files:**
- Create: `backend/app/**`, `backend/tests/**`, `backend/scripts/run_dev.sh`, `backend/scripts/smoke_p0.sh`, `backend/requirements.txt`, `backend/data/catalog.json`, `backend/data/skills/**`

- [ ] **Step 1: Create backend and rsync included trees**

```bash
cd /Users/kean/Desktop/DemoFile/mobile_agent
SRC=.worktrees/cloud-agent-p0/cloud_agent
mkdir -p backend
rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'data/sessions' \
  --exclude 'data/sessions.db' \
  --exclude 'data/sandboxes' \
  --exclude 'data/openvidau.env' \
  --exclude 'data/account_auth.json' \
  --exclude 'data/cloud_sessions.json' \
  --exclude 'data/installed.json' \
  "$SRC/app" "$SRC/tests" "$SRC/scripts" "$SRC/requirements.txt" \
  backend/
mkdir -p backend/data
rsync -a "$SRC/data/catalog.json" "$SRC/data/skills" backend/data/
```

Expected: `backend/app/main.py` and `backend/data/skills/` exist; no `.venv`, no `openvidau.env`.

- [ ] **Step 2: Verify no secrets copied**

```bash
find backend -name 'openvidau.env' -o -name 'sessions.db' -o -name '.venv' | head
# Expected: empty
```

- [ ] **Step 3: Commit**

```bash
git add backend/
git commit -m "$(cat <<'EOF'
chore: move cloud_agent sources into backend/

EOF
)"
```

---

### Task 2: Sanitized sample data + `.gitignore`

**Files:**
- Create: `backend/data/cloud_sessions.json`, `backend/data/account_auth.json`, `backend/data/installed.json`, `backend/.gitignore`

- [ ] **Step 1: Write sanitized JSON**

`cloud_sessions.json` must match `account_store` shape (`{"sessions": {}}`), not a bare array:

```json
{
  "sessions": {}
}
```

`account_auth.json` — placeholder without tokens (loader returns None without `refresh_token`):

```json
{
  "schema_version": 1
}
```

`installed.json` — copy expert skill lists from worktree sample (no secrets); keep structure `{"experts": { "<id>": {"skills": [...], "mcp_servers": [...]} }}` for Creative / TikTok / GEO.

- [ ] **Step 2: Write `backend/.gitignore`**

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
.env
data/sessions.db
data/sessions/
data/sandboxes/
data/openvidau.env
```

- [ ] **Step 3: Commit**

```bash
git add backend/data/*.json backend/.gitignore
git commit -m "$(cat <<'EOF'
chore(backend): add sanitized sample data and gitignore

EOF
)"
```

---

### Task 3: Production deploy artifacts

**Files:**
- Create: `backend/scripts/run_prod.sh`, `backend/Dockerfile`, `backend/docker-compose.yml`, `backend/.env.example`
- Modify: `backend/README.md`

- [ ] **Step 1: Add `scripts/run_prod.sh`**

Same as `run_dev.sh` but without `--reload`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
export CLOUD_AGENT_MCP_MODE="${CLOUD_AGENT_MCP_MODE:-auto}"
export CLOUD_AGENT_SANDBOX_PROVIDER="${CLOUD_AGENT_SANDBOX_PROVIDER:-local}"
export CLOUD_AGENT_LLM_MODE="${CLOUD_AGENT_LLM_MODE:-auto}"
if [[ -x .venv/bin/uvicorn ]]; then UV=.venv/bin/uvicorn; else UV=uvicorn; fi
exec "$UV" app.main:app --host 0.0.0.0 --port 8787
```

- [ ] **Step 2: Add Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
COPY scripts ./scripts
ENV PYTHONPATH=/app
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
```

- [ ] **Step 3: Add `docker-compose.yml`**

```yaml
services:
  cloud-agent:
    build: .
    ports:
      - "8787:8787"
    env_file:
      - .env
    volumes:
      - ./data/sessions.db:/app/data/sessions.db
      - ./data/sessions:/app/data/sessions
      - ./data/sandboxes:/app/data/sandboxes
      - ./data/openvidau.env:/app/data/openvidau.env
      - ./data/account_auth.json:/app/data/account_auth.json
      - ./data/cloud_sessions.json:/app/data/cloud_sessions.json
      - ./data/installed.json:/app/data/installed.json
    restart: unless-stopped
```

Note: ensure host files/dirs exist before compose (README documents `touch` / `mkdir` if needed), or use named volumes for runtime-only paths. Prefer creating empty host stubs in README.

- [ ] **Step 4: Add `.env.example`**

```bash
CLOUD_AGENT_PUBLIC_BASE_URL=https://your-host.example.com
CLOUD_AGENT_ALLOW_DEV_TOKEN=false
CLOUD_AGENT_CORS_ORIGINS=https://your-app.example.com
CLOUD_AGENT_OPENVIDAU_BASE_URL=https://open.vidau.ai
CLOUD_AGENT_OPENVIDAU_CLIENT_APP=vidau-mobile
CLOUD_AGENT_SANDBOX_PROVIDER=local
CLOUD_AGENT_MCP_MODE=auto
CLOUD_AGENT_LLM_MODE=auto
# CLOUD_AGENT_LLM_API_KEY=
# CLOUD_AGENT_LLM_BASE_URL=
# CLOUD_AGENT_LLM_MODEL=
```

- [ ] **Step 5: Rewrite `backend/README.md` as deploy guide**

Include: Docker compose path, venv + `run_prod.sh`, env table, health check, note that Link Gateway is out of scope.

- [ ] **Step 6: Smoke test without Docker (venv)**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
CLOUD_AGENT_ALLOW_DEV_TOKEN=true PYTHONPATH=. pytest tests/test_health.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/run_prod.sh backend/Dockerfile backend/docker-compose.yml \
  backend/.env.example backend/README.md
git commit -m "$(cat <<'EOF'
feat(backend): add Docker and production run scripts

EOF
)"
```

---

### Task 4: Remove worktree `cloud_agent` + update ignore/docs

**Files:**
- Delete: `.worktrees/cloud-agent-p0/cloud_agent/` (entire tree)
- Modify: `.gitignore`, `README.md`, `docs/superpowers/specs/2026-07-11-vidau-cloud-agent-design.md` (and other specs/plans that cite `.worktrees/.../cloud_agent` or root `cloud_agent/` as the start path)

- [ ] **Step 1: Remove worktree backend copy**

```bash
rm -rf .worktrees/cloud-agent-p0/cloud_agent
test ! -d .worktrees/cloud-agent-p0/cloud_agent
```

- [ ] **Step 2: Update root `.gitignore`**

Replace `cloud_agent/...` entries with `backend/...` equivalents:

```gitignore
backend/data/sessions.db
backend/data/sandboxes/
backend/data/sessions/
backend/data/openvidau.env
backend/**/__pycache__/
backend/.venv/
backend/.env
```

- [ ] **Step 3: Update root `README.md`**

Add Cloud Agent section:

```bash
cd backend
cp .env.example .env
docker compose up -d
# or ./scripts/run_dev.sh for local reload
curl http://localhost:8787/health
```

- [ ] **Step 4: Path fix in key docs**

In `docs/superpowers/specs/2026-07-11-vidau-cloud-agent-design.md` §12.5 (and similar entry points): change `cd .worktrees/cloud-agent-p0/cloud_agent` → `cd backend`. Replace remaining `cloud_agent/` deploy-path mentions in attach/session-history design docs where they describe repo layout (not historical plan task lists unless they are the current entry).

- [ ] **Step 5: Final verification**

```bash
test -f backend/app/main.py
test ! -d .worktrees/cloud-agent-p0/cloud_agent
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_health.py -v
# Expected: PASS
git status  # no openvidau.env, no sessions attachments staged
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore README.md docs/superpowers/specs/
git commit -m "$(cat <<'EOF'
docs: point Cloud Agent paths at backend/ and drop worktree copy

EOF
)"
```

Note: worktree deletion may be untracked from main git (`.worktrees/` is gitignored). Confirm main repo only cares about `backend/` presence.

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| Flat `backend/` from worktree | Task 1 |
| Sanitized samples, no secrets | Task 2 |
| Docker + compose + `.env.example` + `run_prod.sh` | Task 3 |
| Remove worktree `cloud_agent/` | Task 4 |
| Docs / README paths | Task 4 |
| Flutter API unchanged | (no Flutter edits) |
| No Link Gateway | (out of scope) |
