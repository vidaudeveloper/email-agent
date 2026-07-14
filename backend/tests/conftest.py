"""Shared pytest fixtures — force mock MCP for deterministic unit tests."""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _force_mock_for_tests(monkeypatch):
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    monkeypatch.setattr(settings, "llm_mode", "stub")
    monkeypatch.setattr(settings, "sandbox_provider", "none")
