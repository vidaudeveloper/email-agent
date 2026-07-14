from typing import Any, Literal, Optional

from pydantic import BaseModel

SandboxPolicy = Literal["never", "on_demand", "always"]
ExpertStatus = Literal["ready", "needs_setup", "needs_auth", "coming_soon"]
ExpertAvailability = Literal["ready", "coming_soon"]


class ExpertListItem(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]
    skills: list[str]
    toolsets: list[str]
    requires_mcp: list[str]
    sandbox_policy: SandboxPolicy
    status: ExpertStatus
    installed: bool = False
    mcp_mode: str = "mock"
    availability: ExpertAvailability = "ready"
    name_i18n: Optional[dict[str, str]] = None
    # Soft hint (desktop-aligned): missing MCP keys do not block chat.
    mcp_credentials_missing: list[str] = []


class ExpertDetail(ExpertListItem):
    activation_prompt: Optional[str] = None
    mcp_servers: list[dict[str, Any]] = []


class ExpertsListResponse(BaseModel):
    experts: list[ExpertListItem]


SessionStatus = Literal["ready", "needs_auth", "needs_setup", "sandbox_starting"]


class SandboxInfo(BaseModel):
    provider: str
    allocated: bool


class SessionCreateRequest(BaseModel):
    expert_id: str


class SessionCreateResponse(BaseModel):
    session_id: str
    status: SessionStatus
    sandbox: SandboxInfo
    missing_credentials: list[str] = []
    mcp_mode: str = "mock"
    llm_mode: str = "stub"
    expert_name: str = ""
