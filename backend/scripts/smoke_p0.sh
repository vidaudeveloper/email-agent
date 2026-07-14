#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://127.0.0.1:8787}"
TOKEN="dev-local-token"
AUTH=(-H "Authorization: Bearer $TOKEN")

health=$(curl -sf "$BASE/health")
echo "$health" | grep -q '"ok":true'
echo "$health" | grep -q '"mcp_mode"'
echo "$health" | grep -q '"llm_configured"'

experts=$(curl -sf "${AUTH[@]}" "$BASE/v1/experts")
echo "$experts" | grep -q tiktok-ads-agent
echo "$experts" | grep -q vidau-creative-agent-oneclick

curl -sf -X POST "${AUTH[@]}" "$BASE/v1/experts/tiktok-ads-agent/install" | grep -q '"ok":true'
curl -sf -X POST "${AUTH[@]}" "$BASE/v1/experts/vidau-creative-agent-oneclick/install" | grep -q '"ok":true'

SID=$(curl -sf "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"expert_id":"tiktok-ads-agent"}' "$BASE/v1/sessions" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'mcp_mode' in d and 'llm_mode' in d; print(d['session_id'])")
test -n "$SID"
echo "smoke ok session=$SID"
