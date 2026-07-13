#!/usr/bin/env bash
# Initialize project-local Hermes (isolated from ~/.hermes).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_DIR="$ROOT/.hermes"

echo "==> email_demo Hermes setup (isolated)"
echo "    Project:     $ROOT"
echo "    HERMES_HOME: $HERMES_DIR"

if [[ ! -d "$ROOT/skills/engage/email-creative-builder" ]]; then
  echo "    Syncing SEND skills from upstream..."
  python3 "$ROOT/scripts/sync-send-skills.py"
fi

mkdir -p "$HERMES_DIR"

if [[ ! -f "$HERMES_DIR/.env" ]]; then
  cp "$ROOT/hermes/.env.example" "$HERMES_DIR/.env"
  echo "    Created $HERMES_DIR/.env — add your Vidau API key"
else
  echo "    Kept existing $HERMES_DIR/.env"
fi

if [[ ! -f "$HERMES_DIR/SOUL.md" ]]; then
  cp "$ROOT/hermes/SOUL.md.template" "$HERMES_DIR/SOUL.md"
  echo "    Created $HERMES_DIR/SOUL.md from template"
else
  echo "    Kept existing $HERMES_DIR/SOUL.md (to refresh: cp hermes/SOUL.md.template .hermes/SOUL.md)"
fi

sed "s|__PROJECT_ROOT__|$ROOT|g" \
  "$ROOT/hermes/config.yaml.template" > "$HERMES_DIR/config.yaml"
echo "    Wrote $HERMES_DIR/config.yaml"

SKILL_COUNT="$(find "$ROOT/skills" -name SKILL.md | wc -l | tr -d ' ')"
echo "    Skills loaded: $SKILL_COUNT SKILL.md files"

echo ""
echo "Next:"
echo "  1. Edit $HERMES_DIR/.env  (VIDAU_API_KEY=...)"
echo "  2. Start:  bash hermes/run.sh chat"
echo "  3. Test:   /email-creative-builder 写一封夏季清仓促销邮件"
