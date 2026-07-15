#!/usr/bin/env python3
"""Rewrite hardcoded email_demo absolute paths to portable $EMAIL_AGENT_ROOT."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "/Users/kean/Desktop/DemoFile/email_demo"
SKIP_DIRS = {".git", ".hermes", ".upstream-aaron-marketing-skills", "node_modules"}


def rewrite_text(text: str) -> str:
    # Absolute Kean path → env var
    text = text.replace(f'python3 "{OLD}/', 'python3 "$EMAIL_AGENT_ROOT/')
    text = text.replace(f"python3 '{OLD}/", "python3 '$EMAIL_AGENT_ROOT/")
    text = text.replace(OLD, "$EMAIL_AGENT_ROOT")
    # Any leftover Windows/Unix absolute pointing into this clone
    text = re.sub(
        r'python3\s+"[^"\n]+/(?:email-agent(?:-gh)?|email_demo)/',
        'python3 "$EMAIL_AGENT_ROOT/',
        text,
    )
    return text


def main() -> int:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.suffix.lower() not in {".md", ".txt", ".sh", ".py", ".yaml", ".yml", ".template"}:
            continue
        if path.name == "fix-skill-paths.py":
            continue
        raw = path.read_text(encoding="utf-8")
        new = rewrite_text(raw)
        if new != raw:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(f"  patched {path.relative_to(ROOT)}")
    print(f"Done. {changed} file(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
