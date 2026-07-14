"""MCP Gateway: mock tools or real MCP over SSE / HTTP JSON-RPC.

TikTok Ads MCP (desktop catalog) uses SSE::

    https://tiktok.vidau.ai/api/mcp/sse?apiKey=<KEY>

Set ``CLOUD_AGENT_MCP_MODE=real`` and ``CLOUD_AGENT_MCP_TIKTOK_URL`` (with or
without apiKey). Prefer storing the key via ``PUT /v1/credentials/tiktok-ads-agent``;
the gateway injects ``apiKey`` into the URL query when missing.

Transport selection:
- URL path contains ``/sse`` or ``CLOUD_AGENT_MCP_TRANSPORT=sse`` → MCP SSE client
- otherwise → HTTP JSON-RPC POST (legacy / custom gateways)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
import yaml

from app.account_store import load_openvidau_env
from app.config import Settings
from app.credentials import get_credential

MOCK_TOOLS: dict[str, list[dict[str, str]]] = {
    "tiktok-ads-agent": [
        {"tool": "create_campaign", "description": "Create a TikTok ad campaign"},
        {"tool": "list_campaigns", "description": "List TikTok ad campaigns"},
        {"tool": "inspect_ads", "description": "Inspect ads for a campaign"},
    ],
    "creative-agent": [
        {"tool": "analyze_image", "description": "Analyze a product or reference image"},
        {"tool": "generate_creative_plan", "description": "Generate a creative plan"},
    ],
    "vidau-geo": [
        {"tool": "geo_audit", "description": "Run a GEO / AI-visibility audit"},
        {"tool": "brand_insights", "description": "Fetch brand GEO insights"},
    ],
}


class McpGatewayError(Exception):
    pass


def _external_tool_name(server: str, tool: str) -> str:
    return f"mcp_{server}_{tool}"


def _strip_prefix(server: str, tool: str) -> str:
    prefix = f"mcp_{server}_"
    if tool.startswith(prefix):
        return tool[len(prefix) :]
    return tool


def inject_api_key(url: str, api_key: str | None) -> str:
    """Ensure ``apiKey`` query param is set when a key is available."""
    if not api_key:
        return url.replace("<YOUR_API_KEY>", "").rstrip("?&")
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    # Replace placeholder values
    existing = (query.get("apiKey") or [None])[0]
    if existing in (None, "", "<YOUR_API_KEY>"):
        query["apiKey"] = [api_key]
    new_query = urlencode({k: v[0] if len(v) == 1 else v for k, v in query.items()}, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _wants_sse(url: str, transport: str) -> bool:
    if transport.strip().lower() == "sse":
        return True
    if transport.strip().lower() in {"http", "jsonrpc"}:
        return False
    path = urlparse(url).path.lower()
    return "/sse" in path


def _wants_streamable_http(url: str, transport: str, server: str) -> bool:
    mode = transport.strip().lower()
    if mode in {"streamable", "streamable_http", "http"}:
        return True
    if mode in {"sse", "jsonrpc"}:
        return False
    # Creative / GEO MCP speak Streamable HTTP
    if server in {"creative-agent", "vidau-geo"}:
        return True
    path = urlparse(url).path.lower()
    return path.endswith("/mcp") and "/sse" not in path


def _vidau_home(settings: Settings) -> Path:
    if settings.vidau_home:
        return Path(settings.vidau_home).expanduser()
    return Path.home() / ".vidau"


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        return {}
    return out


def resolve_vidau_user_id(settings: Settings) -> str:
    """Desktop MCP identity: creative.vidau.ai requires header vidau_user_id."""
    sso = load_openvidau_env()
    for candidate in (
        sso.get("VIDAU_USER_ID", ""),
        os.environ.get("VIDAU_USER_ID", ""),
        _load_dotenv(_vidau_home(settings) / ".env").get("VIDAU_USER_ID", ""),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return ""


def resolve_openvidau_api_key(settings: Settings) -> str:
    sso = load_openvidau_env()
    for candidate in (
        sso.get("OPENVIDAU_API_KEY", ""),
        settings.llm_api_key,
        os.environ.get("OPENVIDAU_API_KEY", ""),
        _load_dotenv(_vidau_home(settings) / ".env").get("OPENVIDAU_API_KEY", ""),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return ""


def resolve_creative_url_from_desktop(settings: Settings) -> str:
    """Prefer ~/.vidau/config.yaml mcp_servers.creative-agent.url when set."""
    cfg_path = _vidau_home(settings) / "config.yaml"
    if not cfg_path.exists():
        return ""
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    servers = data.get("mcp_servers") or {}
    entry = servers.get("creative-agent") or {}
    if isinstance(entry, dict):
        return str(entry.get("url") or "").strip()
    return ""


class McpGateway:
    def __init__(self, settings: Settings, user_id: str = "default"):
        self.settings = settings
        self.user_id = user_id

    async def list_tools(self, server: str) -> list[dict[str, Any]]:
        if self.settings.mcp_mode == "mock" or self.settings.effective_mcp_mode() == "mock":
            return self._mock_list_tools(server)
        return await self._real_list_tools(server)

    async def call_tool(
        self, server: str, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        tool = _strip_prefix(server, tool)
        if self.settings.mcp_mode == "mock" or self.settings.effective_mcp_mode() == "mock":
            return self._mock_call_tool(server, tool, arguments)
        if server == "tiktok-ads-agent":
            url = self._resolve_url(server)
            if "<YOUR_API_KEY>" in url or url.rstrip().endswith("apiKey="):
                raise McpGatewayError(
                    "TikTok Ads MCP 需要 apiKey。可先继续文字问答；"
                    "真实广告数据/创编请在手机专家页配置 MCP Key（云端保存）。"
                )
        return await self._real_call_tool(server, tool, arguments)

    def _mock_list_tools(self, server: str) -> list[dict[str, Any]]:
        stubs = MOCK_TOOLS.get(server, [])
        return [
            {
                "name": _external_tool_name(server, item["tool"]),
                "description": item["description"],
            }
            for item in stubs
        ]

    def _mock_call_tool(
        self, server: str, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        known = {item["tool"] for item in MOCK_TOOLS.get(server, [])}
        if tool not in known:
            raise McpGatewayError(f"Unknown mock tool: {tool}")
        return {
            "ok": True,
            "server": server,
            "tool": tool,
            "arguments": arguments,
            "result": {"message": f"Mock {tool} succeeded"},
        }

    def _resolve_url(self, server: str) -> str:
        if server == "tiktok-ads-agent":
            url = (self.settings.mcp_tiktok_url or "").strip()
            if not url:
                raise McpGatewayError(
                    "CLOUD_AGENT_MCP_TIKTOK_URL is not configured for real MCP mode"
                )
            api_key = get_credential(self.user_id, server)
            resolved = inject_api_key(url, api_key)
            # Keep resolvable for status checks; fail clearly at call time if empty.
            return resolved
        if server == "creative-agent":
            url = (
                resolve_creative_url_from_desktop(self.settings)
                or (self.settings.mcp_creative_url or "").strip()
            )
            if not url:
                raise McpGatewayError(
                    "CLOUD_AGENT_MCP_CREATIVE_URL is not configured for real MCP mode"
                )
            api_key = get_credential(self.user_id, server)
            return inject_api_key(url, api_key)
        if server == "vidau-geo":
            url = (self.settings.mcp_geo_url or "").strip()
            if not url:
                # Prefer desktop config when present
                cfg_path = _vidau_home(self.settings) / "config.yaml"
                if cfg_path.exists():
                    try:
                        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                        entry = (data.get("mcp_servers") or {}).get("vidau-geo") or {}
                        url = str(entry.get("url") or "").strip()
                    except Exception:
                        url = ""
            if not url:
                raise McpGatewayError(
                    "CLOUD_AGENT_MCP_GEO_URL is not configured for real MCP mode"
                )
            api_key = get_credential(self.user_id, server)
            return inject_api_key(url, api_key)
        raise McpGatewayError(f"No MCP URL configured for server: {server}")

    def _auth_headers(self, server: str) -> dict[str, str]:
        """Align with desktop mcp_tool identity headers for Vidau MCP servers."""
        headers: dict[str, str] = {}
        api_key = get_credential(self.user_id, server) or ""
        if not api_key and server in {"creative-agent", "vidau-geo"}:
            # Account identity, not a separate pasted key
            api_key = resolve_openvidau_api_key(self.settings)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        vidau_user_id = resolve_vidau_user_id(self.settings)
        if vidau_user_id:
            headers["vidau_user_id"] = vidau_user_id

        access = os.environ.get("VIDAU_USER_ACCESS_TOKEN", "").strip()
        if not access:
            access = _load_dotenv(_vidau_home(self.settings) / ".env").get(
                "VIDAU_USER_ACCESS_TOKEN", ""
            )
        if access:
            headers["Vidau-user-access-token"] = access

        return headers

    async def _with_sse_session(self, server: str, fn):
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError as exc:
            raise McpGatewayError(
                "mcp package is required for SSE transport. "
                "pip install 'mcp>=1.0'"
            ) from exc

        url = self._resolve_url(server)
        headers = self._auth_headers(server)
        try:
            async with sse_client(
                url,
                headers=headers or None,
                timeout=30.0,
                sse_read_timeout=300.0,
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await fn(session)
        except McpGatewayError:
            raise
        except Exception as exc:
            raise McpGatewayError(f"SSE MCP error ({server}): {exc}") from exc

    async def _with_streamable_http_session(self, server: str, fn):
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise McpGatewayError(
                "mcp package is required for streamable HTTP. "
                "pip install 'mcp>=1.0'"
            ) from exc

        url = self._resolve_url(server)
        headers = self._auth_headers(server)
        if server == "creative-agent" and "vidau_user_id" not in headers:
            raise McpGatewayError(
                "Creative MCP 需要 vidau_user_id（桌面登录后写入 ~/.vidau/.env 的 VIDAU_USER_ID，"
                "或手机 SSO 登录后写入 data/openvidau.env）。"
            )
        if server == "vidau-geo" and "vidau_user_id" not in headers:
            raise McpGatewayError(
                "GEO MCP 需要 vidau_user_id（桌面 ~/.vidau/.env 或手机 SSO 登录）。"
            )
        try:
            async with streamablehttp_client(url, headers=headers or None) as (
                read,
                write,
                _get_session_id,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await fn(session)
        except McpGatewayError:
            raise
        except Exception as exc:
            raise McpGatewayError(
                f"Streamable HTTP MCP error ({server}): {exc}"
            ) from exc

    async def _with_mcp_session(self, server: str, fn):
        url = self._resolve_url(server)
        transport = self.settings.mcp_transport
        if _wants_sse(url, transport):
            return await self._with_sse_session(server, fn)
        if _wants_streamable_http(url, transport, server):
            return await self._with_streamable_http_session(server, fn)
        # legacy JSON-RPC POST
        return None

    async def _jsonrpc(
        self, server: str, method: str, params: dict[str, Any]
    ) -> Any:
        url = self._resolve_url(server)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", **self._auth_headers(server)},
            )
            response.raise_for_status()
            body = response.json()
        if "error" in body:
            raise McpGatewayError(str(body["error"]))
        return body.get("result")

    async def _real_list_tools(self, server: str) -> list[dict[str, Any]]:
        url = self._resolve_url(server)

        async def _list(session):
            result = await session.list_tools()
            return list(result.tools)

        if _wants_sse(url, self.settings.mcp_transport) or _wants_streamable_http(
            url, self.settings.mcp_transport, server
        ):
            tools = await self._with_mcp_session(server, _list)
            return [
                {
                    "name": _external_tool_name(server, t.name),
                    "description": t.description or "",
                }
                for t in tools
            ]

        result = await self._jsonrpc(server, "tools/list", {})
        tools = result.get("tools", result if isinstance(result, list) else [])
        normalized: list[dict[str, Any]] = []
        for item in tools:
            raw_name = item.get("name", "")
            normalized.append(
                {
                    "name": _external_tool_name(server, _strip_prefix(server, raw_name)),
                    "description": item.get("description", ""),
                }
            )
        return normalized

    async def _real_call_tool(
        self, server: str, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        url = self._resolve_url(server)

        async def _call(session):
            return await session.call_tool(tool, arguments=arguments)

        if _wants_sse(url, self.settings.mcp_transport) or _wants_streamable_http(
            url, self.settings.mcp_transport, server
        ):
            result = await self._with_mcp_session(server, _call)
            content_bits: list[str] = []
            for block in getattr(result, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    content_bits.append(text)
            structured = getattr(result, "structuredContent", None) or getattr(
                result, "structured_content", None
            )
            is_error = bool(
                getattr(result, "isError", False) or getattr(result, "is_error", False)
            )
            return {
                "ok": not is_error,
                "server": server,
                "tool": tool,
                "result": structured
                or ("\n".join(content_bits) if content_bits else str(result)),
            }

        result = await self._jsonrpc(
            server,
            "tools/call",
            {"name": tool, "arguments": arguments},
        )
        if isinstance(result, dict) and "ok" in result:
            return result
        return {"ok": True, "result": result}
