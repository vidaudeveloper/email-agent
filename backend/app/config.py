from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLOUD_AGENT_")

    # mock | real | auto (auto → real when any MCP URL configured)
    mcp_mode: str = "auto"
    mcp_tiktok_url: str = "https://tiktok.vidau.ai/api/mcp/sse?apiKey=<YOUR_API_KEY>"
    mcp_creative_url: str = "https://creative.vidau.ai/mcp"
    mcp_geo_url: str = "https://geo.vidau.ai/mcp"
    mcp_transport: str = "auto"
    sandbox_provider: str = "local"
    sandbox_root: str = "data/sandboxes"
    catalog_path: str = "data/catalog.json"
    sqlite_path: str = "data/sessions.db"
    dev_token: str = "dev-local-token"
    # stub | openai_compatible | auto (auto uses openai when LLM config found)
    llm_mode: str = "auto"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_max_turns: int = 8
    cors_origins: str = "*"
    vidau_home: str = ""  # override ~/.vidau
    openvidau_base_url: str = "https://open.vidau.ai"
    openvidau_client_app: str = "vidau-mobile"
    # Keep true for pytest / local smoke; production mobile uses SSO session tokens
    allow_dev_token: bool = True
    # Used to absolutize attachment file URLs in LLM context
    public_base_url: str = "http://127.0.0.1:8787"

    def effective_mcp_mode(self) -> str:
        mode = (self.mcp_mode or "auto").strip().lower()
        if mode in {"mock", "real"}:
            return mode
        # auto
        if self.mcp_tiktok_url or self.mcp_creative_url or self.mcp_geo_url:
            # still mock until credentials replace placeholder — runtime checks
            return "real"
        return "mock"


settings = Settings()
