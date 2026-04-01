"""Tests for core/executor.py — tool execution with timeout."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dietmcp.config.schema import DietMcpConfig
from dietmcp.core.executor import (
    ExecutionError,
    ToolNotFoundError,
    _call_mcp_tool,
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


class TestCallMcpTool:
    """Test the low-level _call_mcp_tool function."""

    @pytest.mark.asyncio
    async def test_text_content_extracted(self, server_config):
        mock_result = _make_call_result("hello world")
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.core.executor.connect") as mock_connect:
            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await _call_mcp_tool(server_config, "read_file", {"path": "/tmp"})

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

            result = await _call_mcp_tool(server_config, "read_file", {})

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
                await _call_mcp_tool(server_config, "slow_tool", {}, timeout=0.1)

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

            tool_result = await _call_mcp_tool(server_config, "get_image", {})

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


class TestGraphQLSchemaCaching:
    """Test GraphQL schema caching to avoid double introspection."""

    @pytest.mark.asyncio
    async def test_schema_caching_avoids_double_introspection(self):
        """Test that schema caching prevents redundant introspection."""
        from dietmcp.models.graphql import (
            GraphQLSchema,
            GraphQLType,
            GraphQLField,
            GraphQLOperation,
            GraphQLArgument,
        )
        from unittest.mock import AsyncMock, MagicMock, patch

        # Setup sample schema with minimal required fields
        test_field = GraphQLField(
            name="getUser",
            description="Get user",
            type_name="User",
            type_kind="OBJECT",
            args=[],
        )

        test_operation = GraphQLOperation(
            name="getUser",
            description="Get user",
            field=test_field,
        )

        sample_schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name=None,
            types={},
            queries=[test_operation],
            mutations=[],
        )

        # Setup config
        config = DietMcpConfig.model_validate({
            "graphqlServers": {
                "github": {
                    "url": "https://api.github.com/graphql",
                    "auth": {"header": "Authorization: Bearer test_token"}
                }
            }
        })

        # Mock introspection to count calls
        with patch("dietmcp.graphql.introspection.GraphQLIntrospector.introspect") as mock_introspect:
            mock_introspect.return_value = sample_schema

            # Mock executor.execute()
            with patch("dietmcp.graphql.executor.GraphQLExecutor.execute") as mock_execute:
                mock_execute.return_value = ToolResult(
                    content=[{"type": "text", "text": '{"data": {"user": "test"}}'}],
                    is_error=False,
                )

                # Mock discover_tools to return tool definition
                with patch("dietmcp.core.executor.discover_tools") as mock_discover:
                    from dietmcp.models.tool import ToolDefinition
                    mock_discover.return_value = [
                        ToolDefinition(
                            name="getUser",
                            description="Get user",
                            input_schema={},
                            server_name="github",
                        )
                    ]

                    # First call should introspect
                    result1 = await execute_tool("github", "getUser", {}, config, protocol="graphql")
                    assert mock_introspect.call_count == 1
                    assert result1.is_error is False

                    # Second call should use cache (no additional introspection)
                    result2 = await execute_tool("github", "getUser", {}, config, protocol="graphql")
                    assert mock_introspect.call_count == 1  # Still 1, not 2
                    assert result2.is_error is False

    @pytest.mark.asyncio
    async def test_schema_cache_invalidation(self):
        """Test that schema cache can be invalidated."""
        from dietmcp.cache.schema_cache import SchemaCache
        from datetime import timedelta

        cache = SchemaCache()

        # Put schema in cache
        test_schema = {"queries": []}
        cache.put("test_key", test_schema)

        # Verify it's cached
        assert cache.get("test_key") == test_schema

        # Invalidate
        cache.invalidate("test_key")

        # Verify it's gone
        assert cache.get("test_key") is None

