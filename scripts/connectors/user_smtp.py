#!/usr/bin/env python3
"""user_smtp.py — send via VidAU/Hermes Messaging Email (IMAP/SMTP) credentials.

Reads the same EMAIL_* vars the VidAU desktop Messaging → Email panel saves
(typically ``%LOCALAPPDATA%/vidau/.env`` on Windows, ``~/.vidau/.env`` elsewhere).
Also accepts already-exported env vars and project ``.hermes/.env``.

SAFETY: mutating ``send`` / ``seed`` are DRY-RUN by default; add ``--live``.
Stdlib only (smtplib + email.mime). Prefer this when the user already configured
personal mail and has no RESEND_API_KEY.

CLI:
  python3 user_smtp.py status
  python3 user_smtp.py send --to a@x --subject S --html file.html [--live]
  python3 user_smtp.py seed --to a@x,b@y --subject S --html file.html [--live]
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Shown to agents/users when Messaging Email is missing.
SETUP_PROMPT_ZH = (
    "尚未配置个人邮箱，无法用你的账号发信。"
    "请打开 VidAU 桌面端 → Messaging → Email，填写邮箱 / SMTP（或 IMAP）/ 密码（Gmail 请用应用专用密码），"
    "点击保存后再重试。也可在 .hermes/.env 中设置 EMAIL_ADDRESS、EMAIL_PASSWORD、EMAIL_SMTP_HOST。"
)
SETUP_PROMPT_EN = (
    "Personal Messaging Email is not configured. "
    "Open VidAU desktop → Messaging → Email, fill address / SMTP (or IMAP) / password "
    "(Gmail: App Password), Save, then retry. "
    "Or set EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_SMTP_HOST in .hermes/.env."
)


def _candidate_env_files() -> list[Path]:
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA") or ""
    files = []
    # VidAU desktop (Messaging Email SSOT on Windows)
    if local:
        files.append(Path(local) / "vidau" / ".env")
        files.append(Path(local) / "hermes" / ".env")
    files.extend([
        home / ".vidau" / ".env",
        home / ".config" / "vidau" / ".env",
        home / ".hermes" / ".env",
    ])
    root = os.environ.get("EMAIL_AGENT_ROOT") or ""
    if root:
        files.append(Path(root) / ".hermes" / ".env")
        files.append(Path(root) / ".env")
    # de-dupe preserving order
    seen = set()
    out = []
    for p in files:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k:
            data[k] = v
    return data


def load_email_config() -> dict:
    """Merge dotenv files (later files do not override earlier) then overlay os.environ."""
    merged: dict[str, str] = {}
    sources: list[str] = []
    for path in _candidate_env_files():
        parsed = _parse_dotenv(path)
        email_keys = {k: v for k, v in parsed.items() if k.startswith("EMAIL_")}
        if not email_keys:
            continue
        # First file that has EMAIL_ADDRESS wins for base; fill missing from later
        if not merged.get("EMAIL_ADDRESS") and email_keys.get("EMAIL_ADDRESS"):
            merged.update(email_keys)
            sources.append(str(path))
        else:
            for k, v in email_keys.items():
                if v and not merged.get(k):
                    merged[k] = v
            sources.append(str(path))

    # Process env always wins
    for k in (
        "EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST",
        "EMAIL_IMAP_PORT", "EMAIL_SMTP_PORT", "EMAIL_HOME_ADDRESS", "EMAIL_ALLOWED_USERS",
    ):
        val = os.environ.get(k)
        if val:
            merged[k] = val

    address = (merged.get("EMAIL_ADDRESS") or "").strip()
    password = merged.get("EMAIL_PASSWORD") or ""
    # Gmail app passwords often stored with spaces — SMTP login accepts without spaces too
    password_login = password.replace(" ", "")
    smtp_host = (merged.get("EMAIL_SMTP_HOST") or "").strip()
    smtp_port = int(merged.get("EMAIL_SMTP_PORT") or 587)
    home = (merged.get("EMAIL_HOME_ADDRESS") or address).strip()

    return {
        "configured": bool(address and password and smtp_host),
        "address": address,
        "password_set": bool(password),
        "password": password,
        "password_login": password_login,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "imap_host": (merged.get("EMAIL_IMAP_HOST") or "").strip(),
        "home_address": home,
        "allowed_users": (merged.get("EMAIL_ALLOWED_USERS") or "").strip(),
        "sources": sources,
    }


def _read_body(value: str | None) -> str:
    if value is None:
        return ""
    if value == "-":
        return sys.stdin.read()
    path = Path(value)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return value


def _split_addrs(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").replace(";", ",").split(",") if p.strip()]


def build_message(*, from_addr: str, to: list[str], subject: str,
                  html: str, text: str, reply_to: str = "") -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))
    elif not text:
        msg.attach(MIMEText("(empty body)", "plain", "utf-8"))
    return msg


def smtp_send(cfg: dict, msg: MIMEMultipart, recipients: list[str]) -> dict:
    host = cfg["smtp_host"]
    port = int(cfg["smtp_port"])
    user = cfg["address"]
    password = cfg["password_login"] or cfg["password"]
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=60)
        else:
            server = smtplib.SMTP(host, port, timeout=60)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(user, password)
        server.sendmail(user, recipients, msg.as_string())
        server.quit()
        return {"ok": True, "error": None, "transport": "user_smtp",
                "smtp_host": host, "smtp_port": port, "from": user, "to": recipients}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "transport": "user_smtp",
                "smtp_host": host, "smtp_port": port, "from": user, "to": recipients}


def cmd_status(_args) -> int:
    cfg = load_email_config()
    payload = {
        "configured": cfg["configured"],
        "address": cfg["address"],
        "password_set": cfg["password_set"],
        "smtp_host": cfg["smtp_host"],
        "smtp_port": cfg["smtp_port"],
        "imap_host": cfg["imap_host"],
        "home_address": cfg["home_address"],
        "sources": cfg["sources"],
        "hint": (
            "Ready — use: python3 user_smtp.py send --to … --subject … --html … [--live]"
            if cfg["configured"] else SETUP_PROMPT_EN
        ),
    }
    if not cfg["configured"]:
        payload["needs_setup"] = True
        payload["user_message_zh"] = SETUP_PROMPT_ZH
        payload["action_for_agent"] = (
            "Stop sending. Tell the user (in Chinese) to configure personal email "
            "via VidAU → Messaging → Email, then re-run status."
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if cfg["configured"] else 2


def cmd_send(args) -> int:
    cfg = load_email_config()
    to_list = _split_addrs(args.to)
    html = _read_body(args.html)
    text = _read_body(args.text)
    from_addr = (args.from_addr or cfg["address"] or "").strip()
    if not cfg["configured"]:
        print(json.dumps({
            "ok": False,
            "needs_setup": True,
            "error": "personal_email_not_configured",
            "user_message_zh": SETUP_PROMPT_ZH,
            "hint": SETUP_PROMPT_EN,
            "action_for_agent": (
                "Do not retry send. Prompt the user to open VidAU → Messaging → Email "
                "and Save their mailbox, then retry."
            ),
        }, ensure_ascii=False, indent=2))
        return 2
    if not to_list:
        print(json.dumps({"ok": False, "error": "missing --to"}, ensure_ascii=False))
        return 2
    bad = [t for t in to_list if t.lower().endswith("@example.com")]
    if bad:
        print(json.dumps({
            "ok": False,
            "error": "placeholder recipients blocked: " + ", ".join(bad),
        }, ensure_ascii=False))
        return 2

    msg = build_message(
        from_addr=from_addr, to=to_list, subject=args.subject,
        html=html, text=text, reply_to=args.reply_to or "",
    )
    preview = {
        "transport": "user_smtp",
        "smtp_host": cfg["smtp_host"],
        "smtp_port": cfg["smtp_port"],
        "from": from_addr,
        "to": to_list,
        "subject": args.subject,
        "html_bytes": len(html.encode("utf-8")),
        "text_bytes": len(text.encode("utf-8")),
    }
    if not args.live:
        print(json.dumps({
            "dry_run": True,
            "request": preview,
            "note": "No SMTP call made. Re-run with --live to execute.",
        }, ensure_ascii=False, indent=2))
        return 0

    result = smtp_send(cfg, msg, to_list)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_seed(args) -> int:
    """One message per recipient (same as send loop)."""
    cfg = load_email_config()
    if not cfg["configured"]:
        print(json.dumps({
            "ok": False,
            "needs_setup": True,
            "error": "personal_email_not_configured",
            "user_message_zh": SETUP_PROMPT_ZH,
            "action_for_agent": (
                "Do not retry send. Prompt the user to configure VidAU → Messaging → Email."
            ),
        }, ensure_ascii=False, indent=2))
        return 2
    recipients = _split_addrs(args.to)
    html = _read_body(args.html)
    text = _read_body(args.text)
    from_addr = (args.from_addr or cfg["address"]).strip()
    results = []
    for to in recipients:
        fake = argparse.Namespace(
            to=to, subject=args.subject, html=None, text=None,
            from_addr=from_addr, reply_to=args.reply_to, live=args.live,
        )
        # inject bodies via temp attrs
        msg = build_message(
            from_addr=from_addr, to=[to], subject=args.subject,
            html=html, text=text, reply_to=args.reply_to or "",
        )
        if not args.live:
            results.append({"dry_run": True, "to": to, "from": from_addr,
                            "subject": args.subject})
            continue
        results.append(smtp_send(cfg, msg, [to]))
    if not args.live:
        print(json.dumps({
            "dry_run": True,
            "count": len(results),
            "items": results,
            "note": "No SMTP call made. Re-run with --live to execute.",
        }, ensure_ascii=False, indent=2))
        return 0
    ok = all(r.get("ok") for r in results)
    print(json.dumps({"ok": ok, "items": results}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="user_smtp.py",
        description="Send via VidAU Messaging Email SMTP credentials (dry-run default).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show whether personal SMTP is configured.")

    live = argparse.ArgumentParser(add_help=False)
    live.add_argument("--live", action="store_true",
                      help="Execute for real (default: dry-run).")

    def add_msg(sp):
        sp.add_argument("--to", required=True, help="Comma-separated recipients.")
        sp.add_argument("--subject", required=True)
        sp.add_argument("--html", default=None,
                        help="HTML body: file path, '-' for stdin, or literal.")
        sp.add_argument("--text", default=None, help="Plain-text body (file / - / literal).")
        sp.add_argument("--from", dest="from_addr", default=None,
                        help="Override From (default: EMAIL_ADDRESS).")
        sp.add_argument("--reply-to", dest="reply_to", default=None)

    s = sub.add_parser("send", parents=[live], help="Send one email via user SMTP.")
    add_msg(s)
    s = sub.add_parser("seed", parents=[live], help="One copy per recipient via user SMTP.")
    add_msg(s)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "send":
        return cmd_send(args)
    if args.command == "seed":
        return cmd_seed(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
