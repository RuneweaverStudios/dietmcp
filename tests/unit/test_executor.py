"""Tests for core/executor.py — tool execution with timeout."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dietmcp.config.schema import DietMcpConfig
from dietmcp.core.executor import (
    ExecutionError,
    ToolNotFoundError,
    _call_tool,
    execute_tool,
)
from dietmcp.models.server import ServerConfig
from dietmcp.models.tool import ToolDefinition, ToolResult


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
def server_config():
    return ServerConfig(name="test-server", command="echo", args=("hello",))


@pytest.fixture
def tool_defs():
    return [
        ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            server_name="test-server",
        ),
    ]


def _make_call_result(text: str, is_error: bool = False) -> MagicMock:
    content_item = MagicMock()
    content_item.text = text
    del content_item.data  # ensure hasattr(item, "data") is False
    result = MagicMock()
    result.content = [content_item]
    result.isError = is_error
    return result


class TestCallTool:
    """Test the low-level _call_tool function."""

    @pytest.mark.asyncio
    async def test_text_content_extracted(self, server_config):
        mock_result = _make_call_result("hello world")
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.executor.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _call_tool(server_config, "read_file", {"path": "/tmp"})

        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "hello world"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_error_result_propagated(self, server_config):
        mock_result = _make_call_result("File not found", is_error=True)
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.executor.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _call_tool(server_config, "read_file", {})

        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_timeout_raises_execution_error(self, server_config):
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(10)

        mock_session = AsyncMock()
        mock_session.call_tool = slow_call
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.executor.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ExecutionError, match="timed out"):
                await _call_tool(server_config, "slow_tool", {}, timeout=0.1)

    @pytest.mark.asyncio
    async def test_binary_content_truncated(self, server_config):
        content_item = MagicMock()
        del content_item.text
        content_item.data = "x" * 500
        result = MagicMock()
        result.content = [content_item]
        result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.executor.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            tool_result = await _call_tool(server_config, "get_image", {})

        assert tool_result.content[0]["type"] == "binary"
        assert len(tool_result.content[0]["data"]) == 200


class TestExecuteTool:
    """Test the high-level execute_tool function."""

    @pytest.mark.asyncio
    async def test_tool_not_found_raises(self, config):
        with patch("dietmcp.core.executor.discover_tools") as mock_discover:
            mock_discover.return_value = [
                ToolDefinition(
                    name="read_file", description="", input_schema={}, server_name="test-server"
                )
            ]

            with pytest.raises(ToolNotFoundError, match="nonexistent"):
                await execute_tool(
                    "test-server", "nonexistent", {}, config
                )

    @pytest.mark.asyncio
    async def test_successful_execution(self, config):
        tool_def = ToolDefinition(
            name="read_file", description="Read", input_schema={}, server_name="test-server"
        )
        mock_result = _make_call_result("file contents")

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with (
            patch("dietmcp.core.executor.discover_tools", return_value=[tool_def]),
            patch("dietmcp.core.executor.connect") as mock_connect,
        ):
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            response = await execute_tool(
                "test-server", "read_file", {"path": "/tmp"}, config
            )

        assert "file contents" in response.content
        assert response.is_error is False
