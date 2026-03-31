"""Tests for core/discovery.py — cache-first tool discovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dietmcp.cache.tool_cache import ToolCache
from dietmcp.config.schema import DietMcpConfig
from dietmcp.core.discovery import discover_tools
from dietmcp.models.server import ServerConfig
from dietmcp.models.tool import ToolDefinition


@pytest.fixture
def config():
    return DietMcpConfig.model_validate({
        "mcpServers": {
            "test-server": {
                "command": "echo",
                "args": ["hello"],
            }
        }
    })


@pytest.fixture
def tool_defs():
    return [
        ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            server_name="test-server",
        ),
        ToolDefinition(
            name="write_file",
            description="Write a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            server_name="test-server",
        ),
    ]


def _make_mock_tool(name: str, description: str, schema: dict) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = schema
    return tool


class TestDiscoverTools:
    """Test the discover_tools function with mocked MCP sessions."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self, config, tool_defs):
        cache = MagicMock(spec=ToolCache)
        cache.get.return_value = tool_defs

        result = await discover_tools("test-server", config, cache=cache)

        assert result == tool_defs
        cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_live(self, config):
        cache = MagicMock(spec=ToolCache)
        cache.get.return_value = None

        mock_tools = [
            _make_mock_tool("read_file", "Read a file", {"type": "object"}),
        ]
        mock_result = MagicMock()
        mock_result.tools = mock_tools

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.discovery.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await discover_tools("test-server", config, cache=cache)

        assert len(result) == 1
        assert result[0].name == "read_file"
        cache.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, config):
        cache = MagicMock(spec=ToolCache)
        cache.get.return_value = [
            ToolDefinition(name="old", description="", input_schema={}, server_name="test-server")
        ]

        mock_result = MagicMock()
        mock_result.tools = [_make_mock_tool("new_tool", "New", {"type": "object"})]

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.discovery.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await discover_tools("test-server", config, force_refresh=True, cache=cache)

        assert result[0].name == "new_tool"
        cache.get.assert_not_called()
        cache.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_without_description_defaults_empty(self, config):
        cache = MagicMock(spec=ToolCache)
        cache.get.return_value = None

        mock_tool = _make_mock_tool("bare_tool", None, {})
        mock_result = MagicMock()
        mock_result.tools = [mock_tool]

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.discovery.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await discover_tools("test-server", config, cache=cache)

        assert result[0].description == ""
