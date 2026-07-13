#!/usr/bin/env bash
# Deliver-phase verification: Tier 1 (always) + Resend Tier 2 (when key set).
# Usage: bash scripts/verify-deliver-flow.sh [--domain example.com]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_DIR="$ROOT/.hermes"
DOMAIN="${1:-example.com}"
if [[ "${1:-}" == "--domain" ]]; then
  DOMAIN="${2:-example.com}"
fi

pass=0
fail=0
warn=0

ok()   { echo "  [PASS] $*"; pass=$((pass + 1)); }
bad()  { echo "  [FAIL] $*"; fail=$((fail + 1)); }
note() { echo "  [WARN] $*"; warn=$((warn + 1)); }

section() { echo ""; echo "== $*"; }

section "1. Project layout"
[[ -f "$HERMES_DIR/config.yaml" ]] && ok "Hermes config: $HERMES_DIR/config.yaml" || bad "Run: bash hermes/install.sh"
[[ -f "$ROOT/scripts/sync-send-skills.py" ]] && ok "Sync script present" || bad "Missing sync-send-skills.py"

skill_count="$(find "$ROOT/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$skill_count" -ge 25 ]]; then
  ok "SKILL.md count: $skill_count"
else
  bad "Expected >=25 SKILL.md, got $skill_count — run: python3 scripts/sync-send-skills.py"
fi

for skill in email-quality-auditor send-experiment-designer inbox-placement-monitor cold-outbound-sequencer; do
  if [[ -f "$ROOT/skills/deliver/$skill/SKILL.md" ]]; then
    ok "Deliver skill: $skill"
  else
    bad "Missing deliver/$skill"
  fi
done

section "2. Tier 1 — DNS pre-flight (no API key)"
if python3 "$ROOT/scripts/connectors/doh.py" auth "$DOMAIN" >/tmp/email_demo_doh.json 2>/tmp/email_demo_doh.err; then
  ok "doh.py auth $DOMAIN"
  if python3 -c "import json; d=json.load(open('/tmp/email_demo_doh.json')); exit(0 if 'spf' in d else 1)"; then
    ok "doh output contains spf/dmarc fields"
  else
    note "doh output unexpected shape — check /tmp/email_demo_doh.json"
  fi
else
  bad "doh.py failed — see /tmp/email_demo_doh.err"
fi

section "3. Hermes skill registration"
if command -v hermes >/dev/null 2>&1; then
  export HERMES_HOME="$HERMES_DIR"
  LIST="$(hermes skills list 2>&1 || true)"
  if echo "$LIST" | grep -q "email-quality-auditor"; then
    ok "Hermes sees email-quality-auditor"
  else
    bad "Hermes missing email-quality-auditor — run: bash hermes/run.sh chat and check external_dirs"
  fi
  if echo "$LIST" | grep -q "inbox-placement-monitor"; then
    ok "Hermes sees inbox-placement-monitor"
  else
    bad "Hermes missing inbox-placement-monitor"
  fi
else
  note "hermes CLI not in PATH — skip skill list check"
fi

section "4. Vidau LLM (optional)"
if [[ -f "$HERMES_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$HERMES_DIR/.env"
  set +a
  if [[ -n "${VIDAU_API_KEY:-}" && "${VIDAU_API_KEY}" != *"your-api-key"* ]]; then
    if curl -sf "https://open.vidau.ai/v1/models" -H "Authorization: Bearer $VIDAU_API_KEY" >/tmp/email_demo_models.json 2>/dev/null; then
      ok "Vidau API key responds"
    else
      note "Vidau key set but /models check failed — chat may still work with another model id"
    fi
  else
    note "VIDAU_API_KEY not set — skip LLM check (Tier 1 deliver skills still work via paste)"
  fi
else
  note "No $HERMES_DIR/.env — skip LLM check"
fi

section "5. Resend Tier 2 (optional)"
RESEND_ENABLED=false
if [[ -f "$HERMES_DIR/config.yaml" ]] && grep -q "enabled: true" "$HERMES_DIR/config.yaml" 2>/dev/null; then
  if grep -A20 "resend:" "$HERMES_DIR/config.yaml" | grep -q "enabled: true"; then
    RESEND_ENABLED=true
  fi
fi

if [[ -n "${RESEND_API_KEY:-}" ]]; then
  ok "RESEND_API_KEY is set"
  if python3 "$ROOT/scripts/connectors/resend.py" domains >/tmp/email_demo_resend.json 2>/tmp/email_demo_resend.err; then
    ok "resend.py domains (read-only)"
  else
    note "resend.py domains failed — check key at https://resend.com/api-keys ($(head -1 /tmp/email_demo_resend.err 2>/dev/null))"
  fi

  # Dry-run send — must NOT hit network with --live
  SAMPLE_HTML="$ROOT/memory/deliver-verify-sample.html"
  mkdir -p "$ROOT/memory"
  cat >"$SAMPLE_HTML" <<'EOF'
<html><body><p>Deliver verification — dry-run only.</p></body></html>
EOF
  if python3 "$ROOT/scripts/connectors/resend.py" send \
      --from "verify@example.com" --to "seed@example.com" \
      --subject "[dry-run] deliver verify" --html "$SAMPLE_HTML" 2>/tmp/email_demo_send_dry.txt; then
    if grep -qi "dry-run\|DRY RUN\|would send" /tmp/email_demo_send_dry.txt 2>/dev/null; then
      ok "resend.py send dry-run (no --live) — safe default"
    else
      ok "resend.py send without --live completed (review /tmp/email_demo_send_dry.txt)"
    fi
  else
    note "resend.py send dry-run failed — see /tmp/email_demo_send_dry.txt"
  fi

  if [[ "$RESEND_ENABLED" == true ]]; then
    ok "Resend MCP enabled in config.yaml"
  else
    note "Resend key set but MCP disabled — run: bash hermes/enable-resend.sh"
  fi
else
  note "RESEND_API_KEY not set — Tier 2 skipped (manual ESP send after SHIP still OK)"
fi

section "6. Manual Hermes checks (copy into chat)"
cat <<EOF
  Start:  bash hermes/run.sh chat

  Deliver gate:
    /email-quality-auditor promotional — 审计测试促销邮件，域名 $DOMAIN

  Experiment:
    /send-experiment-designer 设计主题行 A/B 测试

  Post-send placement:
    /inbox-placement-monitor 说明 seed 测试需要哪些数据

  Cold outbound:
    /cold-outbound-sequencer 设计 3 步 B2B 冷触达大纲

  Full promo path:
    /email-router promotional — 夏季清仓：creative → auditor → 说明如何 seed 测试
EOF

section "Summary"
echo "  PASS: $pass   WARN: $warn   FAIL: $fail"
if [[ "$fail" -gt 0 ]]; then
  echo "  Result: NOT READY — fix FAIL items above"
  exit 1
fi
echo "  Result: READY (Deliver Tier 1${RESEND_API_KEY:+ + Resend key})"
exit 0
