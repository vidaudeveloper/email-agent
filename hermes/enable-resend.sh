#!/usr/bin/env bash
# Enable Resend MCP in project-local Hermes config (requires RESEND_API_KEY in .hermes/.env).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$ROOT/.hermes/config.yaml"
ENV_FILE="$ROOT/.hermes/.env"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG — run: bash hermes/install.sh" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]] || ! grep -q '^RESEND_API_KEY=.\+' "$ENV_FILE" 2>/dev/null; then
  echo "Add RESEND_API_KEY to $ENV_FILE first (https://resend.com/api-keys)" >&2
  exit 1
fi

python3 - <<'PY' "$CONFIG"
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
block = re.search(r"(  resend:\n(?:    .+\n)+)", text)
if not block:
    print("resend: block not found in config.yaml", file=sys.stderr)
    sys.exit(1)
old = block.group(1)
new = re.sub(r"enabled: false", "enabled: true", old, count=1)
if old == new:
    print("Resend MCP already enabled (or pattern mismatch)")
else:
    path.write_text(text.replace(old, new, 1))
    print(f"Enabled Resend MCP in {path}")
PY

echo ""
echo "Next:"
echo "  bash hermes/run.sh chat"
echo "  /reload-mcp"
echo "  python3 scripts/connectors/resend.py domains"
