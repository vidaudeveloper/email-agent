#!/usr/bin/env python3
"""send_mail.py — unified send: prefer VidAU user SMTP, else Resend.

Resolution order:
  1. If EMAIL_ADDRESS + EMAIL_PASSWORD + EMAIL_SMTP_HOST are available
     (VidAU Messaging Email / Hermes .env) → user_smtp.py
  2. Else if RESEND_API_KEY → resend.py
  3. Else print how to configure either path

Same CLI surface for agents:
  python3 send_mail.py status
  python3 send_mail.py send --to … --subject … --html … [--live]
  python3 send_mail.py seed --to … --subject … --html … [--live]

Flags:
  --transport auto|smtp|resend   force a backend (default auto)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _run(script: str, argv: list[str]) -> int:
    cmd = [sys.executable, str(HERE / script), *argv]
    env = os.environ.copy()
    # Ensure connector sibling imports work if any
    return subprocess.call(cmd, env=env)


def resolve_transport(forced: str) -> tuple[str, dict]:
    forced = (forced or "auto").lower()
    # lazy import siblings
    sys.path.insert(0, str(HERE))
    import user_smtp  # noqa: WPS433

    smtp_cfg = user_smtp.load_email_config()
    resend_key = bool((os.environ.get("RESEND_API_KEY") or "").strip())

    info = {
        "smtp_configured": smtp_cfg["configured"],
        "smtp_address": smtp_cfg.get("address") or "",
        "resend_key_set": resend_key,
    }

    if forced == "smtp":
        return "smtp", info
    if forced == "resend":
        return "resend", info
    if smtp_cfg["configured"]:
        return "smtp", info
    if resend_key:
        return "resend", info
    return "none", info


def cmd_status(args) -> int:
    transport, info = resolve_transport(args.transport)
    print(json.dumps({
        "preferred": transport,
        **info,
        "hint": {
            "smtp": "Will use VidAU Messaging Email (user_smtp.py)",
            "resend": "Will use Resend API (resend.py) — set verified from @mail.vidau.ai",
            "none": (
                "No transport. Configure VidAU → Messaging → Email, "
                "or set RESEND_API_KEY for Resend."
            ),
        }.get(transport, ""),
    }, ensure_ascii=False, indent=2))
    return 0 if transport != "none" else 2


def _forward(args, command: str) -> int:
    transport, info = resolve_transport(args.transport)
    if transport == "none":
        print(json.dumps({
            "ok": False,
            "error": "no email transport configured",
            **info,
        }, ensure_ascii=False, indent=2))
        return 2

    forwarded = [command, "--to", args.to, "--subject", args.subject]
    if args.html:
        forwarded += ["--html", args.html]
    if args.text:
        forwarded += ["--text", args.text]
    if args.reply_to:
        forwarded += ["--reply-to", args.reply_to]
    if args.live:
        forwarded.append("--live")

    if transport == "smtp":
        if args.from_addr:
            forwarded += ["--from", args.from_addr]
        print(json.dumps({"using": "user_smtp", **info}, ensure_ascii=False), file=sys.stderr)
        return _run("user_smtp.py", forwarded)

    # resend
    from_addr = args.from_addr or "noreply@mail.vidau.ai"
    forwarded = [
        command,
        "--from", from_addr,
        "--to", args.to,
        "--subject", args.subject,
    ]
    if args.html:
        forwarded += ["--html", args.html]
    if args.text:
        forwarded += ["--text", args.text]
    if args.reply_to:
        forwarded += ["--reply-to", args.reply_to]
    if args.live:
        forwarded.append("--live")
    print(json.dumps({"using": "resend", **info}, ensure_ascii=False), file=sys.stderr)
    return _run("resend.py", forwarded)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="send_mail.py",
        description="Unified mail send: VidAU user SMTP first, else Resend.",
    )
    transport = argparse.ArgumentParser(add_help=False)
    transport.add_argument(
        "--transport", choices=("auto", "smtp", "resend"), default="auto",
        help="Force backend (default: auto = SMTP if Messaging Email configured, else Resend).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", parents=[transport], help="Show which transport will be used.")

    live = argparse.ArgumentParser(add_help=False)
    live.add_argument("--live", action="store_true")

    def add_msg(sp):
        sp.add_argument("--to", required=True)
        sp.add_argument("--subject", required=True)
        sp.add_argument("--html", default=None)
        sp.add_argument("--text", default=None)
        sp.add_argument("--from", dest="from_addr", default=None)
        sp.add_argument("--reply-to", dest="reply_to", default=None)

    s = sub.add_parser("send", parents=[transport, live])
    add_msg(s)
    s = sub.add_parser("seed", parents=[transport, live])
    add_msg(s)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_status(args)
    return _forward(args, args.command)


if __name__ == "__main__":
    raise SystemExit(main())
