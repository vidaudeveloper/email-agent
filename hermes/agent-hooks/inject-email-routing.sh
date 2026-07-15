#!/usr/bin/env bash
# Inject SEND routing context — distinguish generate-only vs explicit send.
set -euo pipefail

payload="$(cat -)"
msg="$(python3 -c '
import json, sys
data = json.loads(sys.argv[1])
extra = data.get("extra") or {}
print(extra.get("user_message") or data.get("user_message") or "")
' "$payload")"

python3 -c '
import json, re, sys

msg = sys.argv[1]
t = msg.lower()
keys = [
    "邮件", "邮箱", "模版", "模板", "发送", "推广", "营销", "投放",
    "email", "template", "send", "newsletter", "campaign", "subject",
    "meta", "mete", "resend", "@", "广告",
]
if not any(k in t for k in keys):
    print("{}")
    raise SystemExit(0)

# Explicit send: 发送给 / 发给 + email-like, or "send to"
has_recipient = bool(re.search(
    r"(发送给|发给|send\s+to|email\s+to)\s*\S*@\S+|@"
    r"[a-z0-9.-]+\.[a-z]{2,}",
    t,
    re.I,
))
send_verbs = any(k in t for k in ("发送给", "发给", "send to", "email to", "真发", "--live"))
generate_only = (not send_verbs) and any(
    k in t for k in ("生成", "写", "做一封", "广告推广", "营销模版", "营销模板", "draft", "write")
)

if generate_only and not has_recipient:
    ctx = """[email_demo routing — GENERATE ONLY]
User asked to CREATE promotional copy, not to send mail.
You MUST:
1. skill_view("email-creative-builder") and write subject + preview + body + CTA for the product they named (e.g. Mete/Meta 智能投放).
2. Do NOT call mcp_resend_send_email / send_mail / resend / user_smtp, or any send tool.
3. Do NOT invent recipients (no recipient@example.com).
4. Do NOT reuse unrelated prior examples (e.g. 夏季清仓 8 折) unless the user asked for that offer.
5. After the draft, ask once: 是否发送？若发送请给出真实收件人邮箱。"""
elif send_verbs or has_recipient:
    ctx = """[email_demo routing — EXPLICIT SEND]
User asked to SEND. You MUST:
1. skill_view("email-router") then confirm consent in memory/consent/.
2. Use ONLY the recipient address the user gave — never *@example.com placeholders.
3. Prefer personal SMTP when VidAU Messaging Email is configured; otherwise Resend from @mail.vidau.ai.
4. Prefer: python3 \"$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py\" send|seed (source .hermes/.env). Dry-run first; --live only after EQS SHIP.
5. NEVER improvise raw smtplib / himalaya / execute_code mail hacks — only send_mail.py / user_smtp.py / resend.py.
6. Creative must match the product the user named this turn — not a stale session promo.
7. EMAIL_AGENT_ROOT must be set (hermes/run.sh exports it)."""
else:
    ctx = """[email_demo routing]
Email-related request. Load skill_view("email-router").
Generate-only → email-creative-builder, no send.
Send only when user gives a real recipient.
Delivery: python3 \"$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py\" (SMTP from Messaging Email first, else Resend)."""

print(json.dumps({"context": ctx}, ensure_ascii=False))
' "$msg"
