"""Install remote expert skills into backend/data/skills/ (cloud host only)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.config import settings

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PACKAGE_ROOT / "data" / "skills"
INSTALLED_FILE = PACKAGE_ROOT / "data" / "installed.json"

# Desktop-installed skill trees → cloud data/skills fallback
_LOCAL_CATEGORY_DIRS = {
    "vidau-creative": "vidau-creative",
    "vidau-geo": "vidau-geo",
    "tiktok-ads": "tiktok-ads",
    "vidau-social-media": "vidau-social-media",
}


class ExpertInstallError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _vidau_home() -> Path:
    if settings.vidau_home:
        return Path(settings.vidau_home).expanduser()
    return Path.home() / ".vidau"


def _load_installed() -> dict[str, Any]:
    if not INSTALLED_FILE.exists():
        return {"experts": {}}
    return json.loads(INSTALLED_FILE.read_text(encoding="utf-8"))


def _save_installed(data: dict[str, Any]) -> None:
    INSTALLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_installed_skills(expert_id: str) -> list[str]:
    data = _load_installed()
    entry = data.get("experts", {}).get(expert_id) or {}
    return list(entry.get("skills") or [])


def is_expert_installed(expert_id: str) -> bool:
    data = _load_installed()
    return expert_id in (data.get("experts") or {})


def _skill_name_from_text(text: str, fallback: str) -> str:
    match = re.search(r"^name:\s*[\"']?([^\"'\n]+)", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    # frontmatter name:
    match = re.search(r"^---\s*\n(?:.*\n)*?name:\s*[\"']?([^\"'\n]+)", text)
    if match:
        return match.group(1).strip()
    return fallback


def _fetch_text(url: str) -> str | None:
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            res = client.get(url)
            if res.status_code == 200:
                return res.text
    except Exception:
        return None
    return None


def _paths_for_source(source: dict[str, Any]) -> list[str]:
    paths = source.get("paths")
    if isinstance(paths, list) and paths:
        return [str(p) for p in paths if str(p).strip()]
    manifest_url = str(source.get("manifest_url") or "").strip()
    if manifest_url:
        text = _fetch_text(manifest_url)
        if text:
            try:
                data = yaml.safe_load(text) or {}
                skills = data.get("skills") or data.get("paths") or []
                if isinstance(skills, list) and skills:
                    out = []
                    for s in skills:
                        if isinstance(s, dict):
                            p = s.get("path") or s.get("id")
                            if p:
                                out.append(str(p))
                        else:
                            out.append(str(s))
                    return out
            except Exception:
                pass
    return []


def _install_one_skill(raw_base: str, path: str, category: str) -> str | None:
    rel = path.strip("/")
    candidates = []
    if rel:
        candidates.append(f"{raw_base.rstrip('/')}/{rel}/SKILL.md")
    candidates.append(f"{raw_base.rstrip('/')}/SKILL.md")
    for url in candidates:
        text = _fetch_text(url)
        if not text:
            continue
        if "name:" not in text[:800] and not text.strip().startswith("---"):
            if len(text) < 40:
                continue
        name = _skill_name_from_text(text, rel.split("/")[-1] if rel else category or "skill")
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-") or "skill"
        dest = SKILLS_DIR / safe
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(text, encoding="utf-8")
        return safe
    return None


def _copy_local_category(category: str) -> list[str]:
    """Copy ~/.vidau/skills/<category>/* into data/skills (cloud host)."""
    folder = _LOCAL_CATEGORY_DIRS.get(category)
    if not folder:
        return []
    src_root = _vidau_home() / "skills" / folder
    if not src_root.exists():
        return []
    names: list[str] = []
    for child in sorted(src_root.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.exists():
            continue
        dest = SKILLS_DIR / child.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(child, dest)
        names.append(child.name)
    return names


def install_expert(expert: dict[str, Any]) -> dict[str, Any]:
    """Download/copy skills onto the cloud host; record install state."""
    if (expert.get("availability") or "ready") == "coming_soon":
        raise ExpertInstallError(
            "该 Expert 即将支持：需要云端 browser 运行时，当前仅可在列表中查看。",
            status_code=403,
        )

    expert_id = expert["id"]
    installed_names: list[str] = []
    errors: list[str] = []

    for source in expert.get("remote_skill_sources") or []:
        raw_base = str(source.get("raw_base_url") or "").strip()
        category = str(source.get("category") or source.get("id") or "skills")
        paths = _paths_for_source(source)
        remote_ok = 0
        if raw_base and paths:
            for path in paths:
                try:
                    name = _install_one_skill(raw_base, path, category)
                    if name:
                        installed_names.append(name)
                        remote_ok += 1
                    else:
                        errors.append(f"could not fetch SKILL.md for path={path!r}")
                except Exception as exc:
                    errors.append(f"{path}: {exc}")
        # Prefer local desktop skill tree when remote incomplete / 429
        if remote_ok == 0 or (paths and remote_ok < max(1, len(paths) // 2)):
            local_names = _copy_local_category(category)
            if local_names:
                installed_names.extend(local_names)
                errors.append(f"used local ~/.vidau/skills/{category} ({len(local_names)} skills)")
            elif not raw_base:
                errors.append(f"source {source.get('id')}: missing raw_base_url and no local skills")

    for sid in expert.get("skills") or []:
        if sid not in installed_names:
            installed_names.append(sid)
    for source in expert.get("remote_skill_sources") or []:
        sid = str(source.get("id") or "").strip()
        if sid and sid not in installed_names:
            installed_names.append(sid)

    seen: set[str] = set()
    unique = []
    for n in installed_names:
        if n not in seen:
            seen.add(n)
            unique.append(n)

    mcp_hints = []
    for server in expert.get("mcp_servers") or []:
        mcp_hints.append(
            {
                "name": server.get("name"),
                "url": (server.get("config") or {}).get("url"),
            }
        )

    data = _load_installed()
    data.setdefault("experts", {})[expert_id] = {
        "skills": unique,
        "mcp_servers": mcp_hints,
    }
    _save_installed(data)

    catalog_path = PACKAGE_ROOT / "data" / "catalog.json"
    by_id: dict[str, Any] = {}
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        by_id = {s["id"]: s for s in (catalog.get("skills") or []) if s.get("id")}
    except Exception:
        by_id = {}
    for sid in unique:
        dest = SKILLS_DIR / sid
        skill_file = dest / "SKILL.md"
        if skill_file.exists():
            continue
        fallback = by_id.get(sid)
        if fallback and fallback.get("body"):
            dest.mkdir(parents=True, exist_ok=True)
            skill_file.write_text(str(fallback["body"]), encoding="utf-8")

    return {
        "ok": True,
        "expert_id": expert_id,
        "skills": unique,
        "mcp_servers": mcp_hints,
        "errors": errors,
        "runtime": "cloud_host",
    }


def load_skill_bodies(skill_ids: list[str], catalog_skills: list[dict]) -> list[str]:
    """Return skill markdown bodies for activation prompt."""
    by_id = {s["id"]: s for s in catalog_skills}
    bodies: list[str] = []
    for sid in skill_ids:
        path = SKILLS_DIR / sid / "SKILL.md"
        if path.exists():
            bodies.append(path.read_text(encoding="utf-8"))
            continue
        if SKILLS_DIR.exists():
            for child in SKILLS_DIR.iterdir():
                skill_file = child / "SKILL.md"
                if skill_file.exists() and (child.name == sid or sid in child.name):
                    bodies.append(skill_file.read_text(encoding="utf-8"))
                    break
            else:
                fallback = by_id.get(sid)
                if fallback and fallback.get("body"):
                    bodies.append(str(fallback["body"]))
        else:
            fallback = by_id.get(sid)
            if fallback and fallback.get("body"):
                bodies.append(str(fallback["body"]))
    return bodies
