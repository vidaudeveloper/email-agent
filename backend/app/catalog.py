import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.credentials import get_credential
from app.expert_install import get_installed_skills, is_expert_installed
from app.models import ExpertDetail, ExpertListItem, ExpertsListResponse

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _catalog_file() -> Path:
    path = Path(settings.catalog_path)
    if path.is_absolute():
        return path
    return PACKAGE_ROOT / path


@lru_cache(maxsize=1)
def _load_catalog() -> dict:
    with open(_catalog_file(), encoding="utf-8") as handle:
        return json.load(handle)


def reload_catalog() -> None:
    _load_catalog.cache_clear()


def load_catalog_skills() -> list[dict]:
    return list(_load_catalog().get("skills") or [])


def get_expert_raw(expert_id: str) -> dict:
    for expert in _load_catalog().get("experts", []):
        if expert["id"] == expert_id:
            return expert
    raise HTTPException(status_code=404, detail="Expert not found")


def _requires_mcp(expert: dict) -> list[str]:
    if expert.get("requires_mcp"):
        return list(expert["requires_mcp"])
    return [s["name"] for s in (expert.get("mcp_servers") or []) if s.get("name")]


def _missing_mcp_credentials(expert: dict, user_id: str = "default") -> list[str]:
    """Servers that need a pasted API key but don't have one yet (non-blocking)."""
    if settings.effective_mcp_mode() == "mock":
        return []
    missing: list[str] = []
    from app.mcp_gateway import McpGateway

    for server in _requires_mcp(expert):
        try:
            url = McpGateway(settings, user_id)._resolve_url(server)
        except Exception:
            continue
        # Creative / GEO use SSO identity headers — not this gate.
        if server in {"creative-agent", "vidau-geo"}:
            continue
        if "<YOUR_API_KEY>" in url and not get_credential(user_id, server):
            missing.append(server)
        elif "apiKey=" in url and (
            url.rstrip().endswith("apiKey=") or "<YOUR_API_KEY>" in url
        ):
            if not get_credential(user_id, server):
                missing.append(server)
    return missing


def _expert_status(expert: dict, user_id: str = "default") -> str:
    """Desktop-aligned: missing TikTok apiKey does not block chat (Skill Q&A first)."""
    if (expert.get("availability") or "ready") == "coming_soon":
        return "coming_soon"

    mode = settings.effective_mcp_mode()
    requires = _requires_mcp(expert)

    needs_remote = bool(expert.get("remote_skill_sources"))
    if needs_remote and not is_expert_installed(expert["id"]):
        if mode == "real":
            return "needs_setup"

    if mode == "mock":
        return "ready"

    # Ensure MCP URLs are resolvable (config present). Auth gaps are soft.
    from app.mcp_gateway import McpGateway

    for server in requires:
        try:
            McpGateway(settings, user_id)._resolve_url(server)
        except Exception:
            return "needs_setup"
    return "ready"


def _to_list_item(expert: dict, user_id: str = "default") -> ExpertListItem:
    requires = _requires_mcp(expert)
    installed = get_installed_skills(expert["id"])
    skills = installed or list(expert.get("skills") or [])
    availability = expert.get("availability") or "ready"
    if availability not in {"ready", "coming_soon"}:
        availability = "ready"
    display_name = expert.get("name") or expert["id"]
    i18n = expert.get("name_i18n") or {}
    if isinstance(i18n, dict) and i18n.get("zh"):
        display_name = str(i18n["zh"])
    return ExpertListItem(
        id=expert["id"],
        name=display_name,
        description=expert.get("description") or "",
        tags=expert.get("tags") or [],
        skills=skills,
        toolsets=expert.get("toolsets") or [],
        requires_mcp=requires,
        sandbox_policy=expert.get("sandbox_policy") or "on_demand",
        status=_expert_status(expert, user_id),
        installed=is_expert_installed(expert["id"]),
        mcp_mode=settings.effective_mcp_mode(),
        availability=availability,  # type: ignore[arg-type]
        name_i18n=expert.get("name_i18n"),
        mcp_credentials_missing=_missing_mcp_credentials(expert, user_id),
    )


def list_experts(user_id: str = "default") -> ExpertsListResponse:
    catalog = _load_catalog()
    return ExpertsListResponse(
        experts=[_to_list_item(expert, user_id) for expert in catalog.get("experts", [])]
    )


def get_expert(expert_id: str, user_id: str = "default") -> ExpertDetail:
    expert = get_expert_raw(expert_id)
    item = _to_list_item(expert, user_id)
    return ExpertDetail(
        **item.model_dump(),
        activation_prompt=expert.get("activation_prompt"),
        mcp_servers=[
            {
                "name": s.get("name"),
                "url": (s.get("config") or {}).get("url"),
            }
            for s in (expert.get("mcp_servers") or [])
        ],
    )
