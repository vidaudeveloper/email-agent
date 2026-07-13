#!/usr/bin/env python3
"""Sync SEND 16 + cross-discipline deps from aaron-marketing-skills upstream."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / ".upstream-aaron-marketing-skills"
REPO = "https://github.com/aaron-he-zhu/aaron-marketing-skills.git"

EMAIL_PHASES = ("setup", "engage", "nurture", "deliver")
PROTOCOL_SKILLS = ("consent-registry", "offer-claims-registry", "memory-management")

CROSS_DISCIPLINE_INFLUENCER = (
    ("discover", "audience-mapper"),
    ("measure", "landing-optimizer"),
    ("measure", "roi-calculator"),
    ("measure", "performance-analyzer"),
    ("measure", "report-generator"),
)

ROOT_FILES = ("CONNECTORS.md", "SECURITY.md", "PRIVACY.md")
REFERENCE_FILES = (
    "send-benchmark.md",
    "auditor-runbook.md",
    "skill-contract.md",
    "state-model.md",
    "humanizer-slop.md",
    "measurement-protocol.md",
    "c3-benchmark.md",
)
REFERENCE_DIRS = ("scoring-rubrics",)

CONNECTORS = (
    "README.md",
    "_http.py",
    "doh.py",
    "resend.py",
    "ledger.py",
    "experiment.py",
)

EMAIL_CROSS_LINK_OLD = "../../../references/cross-discipline/influencer/"
EMAIL_CROSS_LINK_NEW = "../../cross-discipline/influencer/"


def clone_upstream() -> None:
    if (UPSTREAM / ".git").exists():
        subprocess.run(["git", "-C", str(UPSTREAM), "pull", "--ff-only"], check=True)
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO, str(UPSTREAM)],
            check=True,
        )


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def apply_common_substitutions(text: str) -> str:
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))
    text = re.sub(
        r'python3 "/Users/kean/Desktop/DemoFile/email_demo/',
        f'python3 "{ROOT}/',
        text,
    )
    return text


def patch_protocol_skill(text: str) -> str:
    text = text.replace("../../references/", "../../../references/")
    text = text.replace("../../CONNECTORS.md", "../../../CONNECTORS.md")
    text = text.replace("../../SECURITY.md", "../../../SECURITY.md")
    text = text.replace("../../PRIVACY.md", "../../../PRIVACY.md")
    text = text.replace("../../scripts/", "../../../scripts/")
    text = text.replace("../../email/setup/", "../../setup/")
    text = text.replace("../../email/engage/", "../../engage/")
    text = text.replace("../../email/nurture/", "../../nurture/")
    text = text.replace("../../email/deliver/", "../../deliver/")
    text = text.replace("../../ad/", "../../../references/cross-discipline/ad/")
    text = text.replace(
        "../../influencer/", "../../cross-discipline/influencer/"
    )
    text = text.replace(
        "../../seo-geo/", "../../../references/cross-discipline/seo-geo/"
    )
    text = text.replace(
        "../../social/", "../../../references/cross-discipline/social/"
    )
    text = text.replace(
        "../../narrative/", "../../../references/cross-discipline/narrative/"
    )
    text = text.replace(
        "../../launch/", "../../../references/cross-discipline/launch/"
    )
    return text


def patch_email_skill(text: str) -> str:
    text = text.replace("../../../protocol/", "../../protocol/")
    text = text.replace(EMAIL_CROSS_LINK_OLD, EMAIL_CROSS_LINK_NEW)
    text = text.replace(
        "../../../influencer/discover/",
        "../../cross-discipline/influencer/discover/",
    )
    text = text.replace(
        "../../../influencer/measure/",
        "../../cross-discipline/influencer/measure/",
    )
    text = text.replace(
        "../../../../influencer/measure/",
        "../../cross-discipline/influencer/measure/",
    )
    return text


def patch_cross_discipline_influencer(text: str) -> str:
    text = text.replace("../../../references/", "../../../../references/")
    text = text.replace("../../../CONNECTORS.md", "../../../../CONNECTORS.md")
    text = text.replace("../../../SECURITY.md", "../../../../SECURITY.md")
    text = text.replace("../../../protocol/", "../../../../protocol/")
    text = text.replace("../../../ad/", "../../../../references/cross-discipline/ad/")
    text = text.replace(
        "../../../social/", "../../../../references/cross-discipline/social/"
    )
    text = text.replace("../../../email/setup/", "../../../../setup/")
    text = text.replace("../../../email/engage/", "../../../../engage/")
    text = text.replace("../../../email/nurture/", "../../../../nurture/")
    text = text.replace("../../../email/deliver/", "../../../../deliver/")
    text = text.replace(
        "../../activate/",
        "../../../../references/cross-discipline/influencer/activate/",
    )
    text = text.replace(
        "../../plan/",
        "../../../../references/cross-discipline/influencer/plan/",
    )
    return text


def patch_skill_md(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    parts = rel.parts

    if parts[0] == "skills" and parts[1] == "protocol":
        text = patch_protocol_skill(text)
    elif parts[0] == "skills" and parts[1] in EMAIL_PHASES:
        text = patch_email_skill(text)
    elif parts[0] == "skills" and parts[1] == "cross-discipline":
        text = patch_cross_discipline_influencer(text)

    text = apply_common_substitutions(text)
    path.write_text(text, encoding="utf-8")


def patch_markdown_tree(directory: Path, patch_fn) -> None:
    for path in directory.rglob("*.md"):
        if path.name == "SKILL.md":
            continue
        text = path.read_text(encoding="utf-8")
        text = patch_fn(text)
        text = apply_common_substitutions(text)
        path.write_text(text, encoding="utf-8")


def sync_email_skills() -> list[str]:
    installed: list[str] = []
    for phase in EMAIL_PHASES:
        phase_src = UPSTREAM / "email" / phase
        phase_dst = ROOT / "skills" / phase
        phase_dst.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(phase_src.iterdir()):
            if not skill_dir.is_dir():
                continue
            dst = phase_dst / skill_dir.name
            copy_tree(skill_dir, dst)
            patch_skill_md(dst / "SKILL.md")
            patch_markdown_tree(dst, patch_email_skill)
            installed.append(skill_dir.name)
    return installed


def sync_protocol_skills() -> list[str]:
    installed: list[str] = []
    dst_root = ROOT / "skills" / "protocol"
    dst_root.mkdir(parents=True, exist_ok=True)
    for name in PROTOCOL_SKILLS:
        src = UPSTREAM / "protocol" / name
        dst = dst_root / name
        copy_tree(src, dst)
        patch_skill_md(dst / "SKILL.md")
        patch_markdown_tree(dst, patch_protocol_skill)
        installed.append(name)
    return installed


def sync_cross_discipline_skills() -> list[str]:
    installed: list[str] = []
    for phase, name in CROSS_DISCIPLINE_INFLUENCER:
        src = UPSTREAM / "influencer" / phase / name
        dst = ROOT / "skills" / "cross-discipline" / "influencer" / phase / name
        copy_tree(src, dst)
        patch_skill_md(dst / "SKILL.md")
        patch_markdown_tree(dst, patch_cross_discipline_influencer)
        installed.append(name)
    return installed


def sync_references() -> None:
    ref_dst = ROOT / "references"
    ref_dst.mkdir(parents=True, exist_ok=True)
    for name in REFERENCE_FILES:
        src = UPSTREAM / "references" / name
        if src.exists():
            shutil.copy2(src, ref_dst / name)
    for dirname in REFERENCE_DIRS:
        src = UPSTREAM / "references" / dirname
        dst = ref_dst / dirname
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    cross = ref_dst / "cross-discipline"
    cross.mkdir(parents=True, exist_ok=True)
    readme = cross / "README.md"
    readme.write_text(
        "# Cross-discipline references\n\n"
        "Stub pointers for skills not installed in this email-focused project. "
        "Installed cross-discipline skills live under `skills/cross-discipline/`.\n",
        encoding="utf-8",
    )


def sync_root_files() -> None:
    for name in ROOT_FILES:
        src = UPSTREAM / name
        if src.exists():
            shutil.copy2(src, ROOT / name)


def sync_connectors() -> None:
    dst = ROOT / "scripts" / "connectors"
    dst.mkdir(parents=True, exist_ok=True)
    for name in CONNECTORS:
        src = UPSTREAM / "scripts" / "connectors" / name
        if src.exists():
            shutil.copy2(src, dst / name)


def init_memory() -> None:
    memory = ROOT / "memory"
    dirs = (
        memory / "consent",
        memory / "claims",
        memory / "audits" / "email",
        memory / "email" / "deliverability-qa",
        memory / "influencer" / "audience-mapper",
        memory / "ad" / "landing-optimizer",
        memory / "archive",
    )
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    if not (memory / "claims" / "candidates.md").exists():
        (memory / "claims" / "candidates.md").write_text(
            "# Claim candidates\n\n"
            "Drop `[needs source]` flags from creative skills here.\n",
            encoding="utf-8",
        )
    if not (memory / "claims" / "offers.md").exists():
        (memory / "claims" / "offers.md").write_text(
            "# Live offers\n\n"
            "| offer | terms | start | end | landing | status |\n"
            "|-------|-------|-------|-----|---------|--------|\n",
            encoding="utf-8",
        )
    if not (memory / "audits" / "gdpr-purges.md").exists():
        (memory / "audits" / "gdpr-purges.md").write_text(
            "# GDPR erasure log\n\n"
            "Record prior erasure requests checked by consent-registry.\n",
            encoding="utf-8",
        )


def main() -> int:
    print(f"==> Syncing skills into {ROOT}")
    clone_upstream()
    email = sync_email_skills()
    protocol = sync_protocol_skills()
    cross = sync_cross_discipline_skills()
    sync_references()
    sync_root_files()
    sync_connectors()
    init_memory()
    total = len(email) + len(protocol) + len(cross) + 1  # + email-router
    print(f"    Email SEND ({len(email)}): {', '.join(email)}")
    print(f"    Protocol ({len(protocol)}): {', '.join(protocol)}")
    print(f"    Cross-discipline ({len(cross)}): {', '.join(cross)}")
    print(f"    Total SKILL.md: {total} (incl. email-router)")
    print("    Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
