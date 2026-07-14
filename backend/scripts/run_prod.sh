#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.

export CLOUD_AGENT_MCP_MODE="${CLOUD_AGENT_MCP_MODE:-auto}"
export CLOUD_AGENT_SANDBOX_PROVIDER="${CLOUD_AGENT_SANDBOX_PROVIDER:-local}"
export CLOUD_AGENT_LLM_MODE="${CLOUD_AGENT_LLM_MODE:-auto}"

if [[ "${CLOUD_AGENT_MCP_MODE}" == "mock" ]]; then
  echo "[cloud-agent] WARNING: MCP_MODE=mock — Expert tools are simulated, not real." >&2
else
  echo "[cloud-agent] MCP_MODE=${CLOUD_AGENT_MCP_MODE} (effective real when URLs set)." >&2
fi

if [[ -z "${OPENVIDAU_API_KEY:-}${CLOUD_AGENT_LLM_API_KEY:-}${OPENAI_API_KEY:-}" ]]; then
  echo "[cloud-agent] WARNING: No LLM API key in env. Will try ~/.vidau / data/openvidau.env; otherwise Expert loop cannot run." >&2
fi

if [[ -x .venv/bin/uvicorn ]]; then
  UV=.venv/bin/uvicorn
else
  UV=uvicorn
fi
exec "$UV" app.main:app --host 0.0.0.0 --port 8787
