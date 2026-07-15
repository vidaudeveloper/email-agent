#!/usr/bin/env bash
# Block SMTP improvisation AND unsafe Resend sends (placeholders / wrong domain / generate-only).
set -euo pipefail

payload="$(cat -)"
python3 -c '
import json, sys, re

raw = sys.argv[1]
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("{}")
    raise SystemExit(0)

tool = (data.get("tool_name") or "").lower()
inp = data.get("tool_input") or {}
if not isinstance(inp, dict):
    inp = {}

parts = [json.dumps(inp, ensure_ascii=False)]
for key in ("code", "command", "script", "content", "source", "to", "from", "html", "text", "subject"):
    val = inp.get(key)
    if isinstance(val, str):
        parts.append(val)
    elif isinstance(val, list):
        parts.extend(str(x) for x in val)
blob = "\n".join(parts).lower()

# 1) Block improvised SMTP / smtplib — allow approved connectors only
smtp_hit = bool(re.search(
    r"(smtplib|smtp\.|smtp\(|starttls|email\.mime|"
    r"smtp\.example\.com|mail\.smtp)",
    blob,
))
approved = ("user_smtp.py" in blob) or ("send_mail.py" in blob) or ("connectors/user_smtp" in blob) or ("connectors/send_mail" in blob)
if tool in {"execute_code", "terminal", "run_terminal_cmd", "bash"} and smtp_hit and not approved:
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Blocked: raw SMTP/smtplib is forbidden. "
            "Use python3 \"$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py\" send|seed "
            "(auto: VidAU Messaging Email SMTP if configured, else Resend). "
            "Dry-run first; --live only after EQS SHIP."
        ),
    }, ensure_ascii=False))
    raise SystemExit(0)

# 2) Block MCP / CLI sends to placeholders or unverified Resend root domain
is_send = (
    "send_email" in tool
    or "resend_send" in tool
    or (
        tool in {"terminal", "execute_code", "bash", "run_terminal_cmd"}
        and (
            ("resend.py" in blob and " send" in f" {blob}")
            or ("send_mail.py" in blob and (" send" in f" {blob}" or " seed" in f" {blob}"))
            or ("user_smtp.py" in blob and (" send" in f" {blob}" or " seed" in f" {blob}"))
        )
    )
)

def recipients():
    found = []
    for key in ("to", "recipient", "recipients", "email"):
        val = inp.get(key)
        if isinstance(val, str):
            found.append(val.lower())
        elif isinstance(val, list):
            found.extend(str(x).lower() for x in val)
    found += re.findall(r"[\w.+-]+@[\w.-]+", blob)
    return found

if is_send:
    recips = recipients()
    bad = [r for r in recips if r.endswith("@example.com") or r in {
        "recipient@example.com", "test@example.com", "user@example.com"
    }]
    if bad:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "Blocked: placeholder recipient "
                + ", ".join(bad)
                + ". Ask the user for a real address (e.g. xubin@vidau.ai). "
                "Generate-only requests must not send."
            ),
        }, ensure_ascii=False))
        raise SystemExit(0)

    # from must not be bare @vidau.ai when using Resend; user SMTP may use personal Gmail
    if "resend.py" in blob or "transport resend" in blob or "--transport resend" in blob:
        froms = []
        for key in ("from", "sender", "from_email"):
            val = inp.get(key)
            if isinstance(val, str):
                froms.append(val.lower())
        froms += re.findall(r"from[\"\s:=]+([\w.+-]+@[\w.-]+)", blob)
        for f in froms:
            if f.endswith("@vidau.ai") and not f.endswith("@mail.vidau.ai"):
                print(json.dumps({
                    "decision": "block",
                    "reason": (
                        "Blocked: from-domain vidau.ai is not verified on Resend. "
                        "Use mail.vidau.ai, or send via user SMTP "
                        "(send_mail.py / user_smtp.py with Messaging Email)."
                    ),
                }, ensure_ascii=False))
                raise SystemExit(0)

print("{}")
' "$payload"
