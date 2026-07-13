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

# 1) Block SMTP / smtplib
smtp_hit = bool(re.search(
    r"(smtplib|smtp\.|smtp\(|starttls|email\.mime|"
    r"smtp\.example\.com|mail\.smtp)",
    blob,
))
if tool in {"execute_code", "terminal", "run_terminal_cmd", "bash"} and smtp_hit:
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Blocked: raw SMTP/smtplib is forbidden. "
            "Use python3 scripts/connectors/resend.py send|seed "
            "(source .hermes/.env; --live only after EQS SHIP). "
            "Verified domain: mail.vidau.ai."
        ),
    }, ensure_ascii=False))
    raise SystemExit(0)

# 2) Block Resend MCP / CLI sends to placeholders or unverified root domain
is_send = (
    "send_email" in tool
    or "resend_send" in tool
    or (tool in {"terminal", "execute_code", "bash"} and "resend.py" in blob and " send" in f" {blob}")
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

    # from must not be bare @vidau.ai (unverified); require mail.vidau.ai
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
                    "Use an address on mail.vidau.ai (e.g. noreply@mail.vidau.ai)."
                ),
            }, ensure_ascii=False))
            raise SystemExit(0)

print("{}")
' "$payload"
