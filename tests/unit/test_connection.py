"""Tests for transport/connection.py — MCP connection management."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dietmcp.models.server import ServerConfig
from dietmcp.transport.connection import ConnectionError, connect


@pytest.fixture
def stdio_config():
    return ServerConfig(
        name="test-stdio",
        command="echo",
        args=("hello",),
        env={"TEST_VAR": "test_value"},
    )


@pytest.fixture
def sse_config():
    return ServerConfig(
        name="test-sse",
        url="https://example.com/mcp/sse",
        headers={"Authorization": "Bearer token"},
    )


@pytest.fixture
def invalid_config():
    return ServerConfig(name="invalid")


class TestConnect:
    """Test the connect context manager dispatch."""

    @pytest.mark.asyncio
    async def test_invalid_config_raises(self, invalid_config):
        with pytest.raises(ConnectionError, match="neither 'command' nor 'url'"):
            async with connect(invalid_config):
                pass

    @pytest.mark.asyncio
    async def test_stdio_merges_env(self, stdio_config):
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        with patch("dietmcp.transport.connection.stdio_client") as mock_stdio:
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(MagicMock(), MagicMock())
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("dietmcp.transport.connection.ClientSession") as mock_cs:
                mock_cs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_cs.return_value.__aexit__ = AsyncMock(return_value=False)

                async with connect(stdio_config) as session:
                    assert session is mock_session

            # Verify StdioServerParameters were constructed with merged env
            call_args = mock_stdio.call_args
            params = call_args[0][0]
            assert params.env["TEST_VAR"] == "test_value"

    @pytest.mark.asyncio
    async def test_stdio_connection_failure_wraps(self, stdio_config):
        with patch("dietmcp.transport.connection.stdio_client") as mock_stdio:
            mock_stdio.return_value.__aenter__ = AsyncMock(
                side_effect=OSError("Process crashed")
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ConnectionError, match="Failed to connect"):
                async with connect(stdio_config):
                    pass

    @pytest.mark.asyncio
    async def test_sse_missing_package_raises(self, sse_config):
        with patch.dict("sys.modules", {"mcp.client.sse": None}):
            with patch("dietmcp.transport.connection._connect_sse") as mock_sse:
                mock_sse.side_effect = ConnectionError(
                    "SSE transport requires the 'httpx-sse' package."
                )
                with pytest.raises(ConnectionError, match="httpx-sse"):
                    async with connect(sse_config):
                        pass
