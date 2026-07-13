#!/usr/bin/env bash
# Run Hermes with email_demo's isolated HERMES_HOME (never uses ~/.hermes).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export HERMES_HOME="$ROOT/.hermes"

if [[ ! -f "$HERMES_HOME/config.yaml" ]]; then
  echo "Missing $HERMES_HOME/config.yaml — run: bash hermes/install.sh" >&2
  exit 1
fi

if ! command -v hermes >/dev/null 2>&1; then
  echo "Hermes CLI not found. Install: https://hermes-agent.nousresearch.com/docs/user-guide/configuration" >&2
  exit 1
fi

# Load project secrets for connectors + MCP (RESEND_API_KEY, etc.)
if [[ -f "$HERMES_HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$HERMES_HOME/.env"
  set +a
fi

# Sync agent-hooks into HERMES_HOME (hooks resolve relative to config / absolute paths)
HOOK_SRC="$ROOT/hermes/agent-hooks"
HOOK_DST="$HERMES_HOME/agent-hooks"
mkdir -p "$HOOK_DST"
if [[ -d "$HOOK_SRC" ]]; then
  cp -f "$HOOK_SRC"/*.sh "$HOOK_DST/" 2>/dev/null || true
  chmod +x "$HOOK_DST"/*.sh 2>/dev/null || true
fi

# Default: preload email-router on `chat` so NL requests get the skill injected.
# Skip if user already passed -s/--skills, or HERMES_NO_PRELOAD_ROUTER=1.
if [[ "${1:-}" == "chat" && "${HERMES_NO_PRELOAD_ROUTER:-}" != "1" ]]; then
  has_skills=0
  for a in "$@"; do
    case "$a" in
      -s|--skills|-s=*|--skills=*) has_skills=1; break ;;
    esac
  done
  if [[ "$has_skills" -eq 0 ]]; then
    set -- chat --skills email-router "${@:2}"
  fi
fi

exec hermes "$@"
