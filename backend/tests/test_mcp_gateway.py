import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.mcp_gateway import McpGateway, McpGatewayError, inject_api_key

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-local-token"}


@pytest.mark.asyncio
async def test_mock_list_and_call_tool():
    gw = McpGateway(Settings(mcp_mode="mock"))
    tools = await gw.list_tools("tiktok-ads-agent")
    names = [t["name"] for t in tools]
    assert "mcp_tiktok-ads-agent_create_campaign" in names or any(
        "create_campaign" in n for n in names
    )
    result = await gw.call_tool("tiktok-ads-agent", "create_campaign", {"name": "test"})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_mock_list_tools_includes_all_stubs():
    gw = McpGateway(Settings(mcp_mode="mock"))
    tools = await gw.list_tools("tiktok-ads-agent")
    names = [t["name"] for t in tools]
    for tool in ("create_campaign", "list_campaigns", "inspect_ads"):
        assert any(tool in n for n in names)


@pytest.mark.asyncio
async def test_real_mode_requires_url():
    gw = McpGateway(Settings(mcp_mode="real", mcp_tiktok_url=""))
    with pytest.raises(McpGatewayError, match="MCP_TIKTOK_URL"):
        await gw.list_tools("tiktok-ads-agent")


def test_inject_api_key_replaces_placeholder():
    url = "https://tiktok.vidau.ai/api/mcp/sse?apiKey=<YOUR_API_KEY>"
    out = inject_api_key(url, "secret-123")
    assert "secret-123" in out
    assert "<YOUR_API_KEY>" not in out


def test_put_credentials():
    r = client.put(
        "/v1/credentials/tiktok-ads-agent",
        json={"api_key": "test-key-123"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["server"] == "tiktok-ads-agent"


def test_put_credentials_requires_auth():
    r = client.put(
        "/v1/credentials/tiktok-ads-agent",
        json={"api_key": "test-key-123"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_real_sse_list_tools_mocked(monkeypatch):
    """SSE path uses mcp ClientSession; mock the session factory."""

    class FakeTool:
        def __init__(self, name, description=""):
            self.name = name
            self.description = description

    class FakeListResult:
        tools = [FakeTool("create_campaign", "Create campaign")]

    class FakeSession:
        async def initialize(self):
            return None

        async def list_tools(self):
            return FakeListResult()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class FakeSseCM:
        async def __aenter__(self):
            return (None, None)

        async def __aexit__(self, *args):
            return None

    async def fake_with_sse(self, server, fn):
        return await fn(FakeSession())

    monkeypatch.setattr(McpGateway, "_with_sse_session", fake_with_sse)
    gw = McpGateway(
        Settings(
            mcp_mode="real",
            mcp_tiktok_url="https://example.com/api/mcp/sse",
            mcp_transport="sse",
        )
    )
    tools = await gw.list_tools("tiktok-ads-agent")
    assert tools[0]["name"] == "mcp_tiktok-ads-agent_create_campaign"
