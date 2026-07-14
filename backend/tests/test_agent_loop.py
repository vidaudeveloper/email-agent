"""Unit tests for agent_loop helpers (no live LLM)."""

from app.agent_loop import _parse_tool_name, build_system_prompt


def test_parse_tool_name_tiktok():
    assert _parse_tool_name("mcp_tiktok_ads_agent_create_campaign") == (
        "tiktok-ads-agent",
        "create_campaign",
    )


def test_parse_tool_name_creative():
    assert _parse_tool_name("mcp_creative_agent_generate") == (
        "creative-agent",
        "generate",
    )


def test_build_system_prompt_includes_activation():
    expert = {
        "id": "tiktok-ads-agent",
        "name": "TikTok Ads Expert",
        "activation_prompt": "You are TikTok Ads.",
        "skills": ["tiktok-ads-skills"],
        "remote_skill_sources": [],
    }
    prompt = build_system_prompt(expert)
    assert "TikTok Ads Expert" in prompt
    assert "You are TikTok Ads." in prompt
    assert "mcp_*" in prompt
