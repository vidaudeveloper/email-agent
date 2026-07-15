#!/usr/bin/env python3
"""send_mail.py — unified send: prefer VidAU user SMTP, else explicit Resend.

Resolution order (auto):
  1. If EMAIL_ADDRESS + EMAIL_PASSWORD + EMAIL_SMTP_HOST are available
     (VidAU Messaging Email / Hermes .env) → user_smtp.py
  2. Else → stop and prompt the user to configure personal email
     (do NOT silently fall back to Resend)

Force Resend only with: --transport resend (requires RESEND_API_KEY).

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
    return subprocess.call(cmd, env=env)


def _setup_payload(info: dict) -> dict:
    sys.path.insert(0, str(HERE))
    import user_smtp  # noqa: WPS433

    return {
        "ok": False,
        "needs_setup": True,
        "error": "personal_email_not_configured",
        "user_message_zh": user_smtp.SETUP_PROMPT_ZH,
        "hint": user_smtp.SETUP_PROMPT_EN,
        "action_for_agent": (
            "Stop. Tell the user in Chinese to configure personal email: "
            "VidAU 桌面端 → Messaging → Email → 填写并保存，然后重试。"
            " Do not invent a Resend key requirement unless they explicitly ask for Resend."
        ),
        "how_to": {
            "desktop": "VidAU → Messaging → Email → Save",
            "env_keys": ["EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_SMTP_HOST"],
            "optional_resend": (
                "Only if the user insists on ESP send: "
                "set RESEND_API_KEY and re-run with --transport resend"
            ),
        },
        **info,
    }


def resolve_transport(forced: str) -> tuple[str, dict]:
    forced = (forced or "auto").lower()
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
        return ("smtp" if smtp_cfg["configured"] else "none"), info
    if forced == "resend":
        return ("resend" if resend_key else "none"), info
    # auto: personal SMTP only; missing → prompt setup (no silent Resend)
    if smtp_cfg["configured"]:
        return "smtp", info
    return "none", info


def cmd_status(args) -> int:
    transport, info = resolve_transport(args.transport)
    if transport == "smtp":
        print(json.dumps({
            "preferred": "smtp",
            **info,
            "hint": "Will use VidAU Messaging Email (user_smtp.py)",
        }, ensure_ascii=False, indent=2))
        return 0
    if transport == "resend":
        print(json.dumps({
            "preferred": "resend",
            **info,
            "hint": "Will use Resend API (resend.py) — from @mail.vidau.ai",
            "note": (
                "Personal Messaging Email is still recommended. "
                "Configure VidAU → Messaging → Email when possible."
            ),
        }, ensure_ascii=False, indent=2))
        return 0

    # none — always prompt personal email setup on auto/smtp miss
    payload = {
        "preferred": "none",
        **_setup_payload(info),
    }
    if args.transport == "resend" and not info.get("resend_key_set"):
        payload["error"] = "resend_not_configured"
        payload["user_message_zh"] = (
            "未配置 Resend。请先在 VidAU → Messaging → Email 配置个人邮箱（推荐），"
            "或在 .hermes/.env 设置 RESEND_API_KEY 后再用 --transport resend。"
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2


def _forward(args, command: str) -> int:
    transport, info = resolve_transport(args.transport)
    if transport == "none":
        print(json.dumps(_setup_payload(info), ensure_ascii=False, indent=2))
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
        description="Unified mail send: VidAU user SMTP first; prompt setup if missing.",
    )
    transport = argparse.ArgumentParser(add_help=False)
    transport.add_argument(
        "--transport", choices=("auto", "smtp", "resend"), default="auto",
        help="auto/smtp need Messaging Email; resend needs RESEND_API_KEY.",
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
