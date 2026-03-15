"""MCP client connection management.

DEV NOTES:
- This module is the sole point of contact with the MCP Python SDK's transport
  layer. If the SDK changes its API, only this file needs updating.
- We shadow Python's built-in ConnectionError with our own. This is intentional:
  all connection failures should be caught as dietmcp.transport.connection.ConnectionError,
  not the builtin. Import carefully.
- SSE import is lazy (inside _connect_sse) because httpx-sse is an optional
  dependency. Most users only need stdio transport.
- The child process environment (line 51-52) merges os.environ with config.env.
  This ensures the MCP server process inherits PATH and other system variables
  while also getting the resolved credentials from config.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from dietmcp.models.server import ServerConfig


class ConnectionError(Exception):
    """Raised when connection to an MCP server fails."""


@asynccontextmanager
async def connect(config: ServerConfig) -> AsyncIterator[ClientSession]:
    """Open a managed connection to an MCP server.

    Supports stdio transport (command + args) and SSE transport (url).
    The connection is automatically closed when the context manager exits.

    Args:
        config: Resolved server configuration with credentials interpolated.

    Yields:
        An initialized MCP ClientSession.

    Raises:
        ConnectionError: If the server cannot be reached or initialized.
    """
    if config.is_stdio:
        async with _connect_stdio(config) as session:
            yield session
    elif config.is_sse:
        async with _connect_sse(config) as session:
            yield session
    else:
        raise ConnectionError(
            f"Server '{config.name}' has neither 'command' nor 'url' configured."
        )


@asynccontextmanager
async def _connect_stdio(config: ServerConfig) -> AsyncIterator[ClientSession]:
    """Connect to an MCP server over stdio transport."""
    # Build the environment for the child process
    child_env = dict(os.environ)
    child_env.update(config.env)

    params = StdioServerParameters(
        command=config.command,
        args=list(config.args),
        env=child_env,
    )

    try:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
    except Exception as exc:
        raise ConnectionError(
            f"Failed to connect to stdio server '{config.name}' "
            f"(command: {config.command}): {exc}"
        ) from exc


@asynccontextmanager
async def _connect_sse(config: ServerConfig) -> AsyncIterator[ClientSession]:
    """Connect to an MCP server over SSE transport."""
    try:
        from mcp.client.sse import sse_client
    except ImportError as exc:
        raise ConnectionError(
            "SSE transport requires the 'httpx-sse' package. "
            "Install it with: pip install httpx-sse"
        ) from exc

    try:
        async with sse_client(
            url=config.url,
            headers=config.headers,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
    except Exception as exc:
        raise ConnectionError(
            f"Failed to connect to SSE server '{config.name}' "
            f"(url: {config.url}): {exc}"
        ) from exc
