"""Tool discovery from MCP servers.

DEV NOTES:
- Discovery is the most frequently called core function. Every exec and skills
  call goes through discover_tools first (for tool validation/generation).
- The cache-first pattern here is critical for performance: live MCP discovery
  takes ~2s (server spawn + initialize + list_tools), while cache reads are <0.1ms.
- We intentionally create a fresh connection per invocation rather than holding
  a persistent connection. This trades slight latency for simplicity and avoids
  stale connection bugs. The cache layer makes this acceptable since most calls
  are cache hits.
- The MCP SDK's Tool object has an `inputSchema` attribute (camelCase, matching
  the JSON-RPC spec). We normalize this into our ToolDefinition model.
"""

from __future__ import annotations

from dietmcp.cache.tool_cache import ToolCache
from dietmcp.config.loader import DietMcpConfig, get_server_config
from dietmcp.models.tool import ToolDefinition
from dietmcp.transport.connection import connect


async def discover_tools(
    server_name: str,
    config: DietMcpConfig,
    force_refresh: bool = False,
    cache: ToolCache | None = None,
) -> list[ToolDefinition]:
    """Discover available tools from an MCP server.

    Checks the cache first unless force_refresh is True. On cache miss,
    connects to the server, fetches tools, and populates the cache.

    Args:
        server_name: Name of the server as defined in config.
        config: Full application configuration.
        force_refresh: If True, bypass cache and fetch fresh.
        cache: Optional cache instance (uses default if None).

    Returns:
        List of ToolDefinition models.
    """
    server_config = get_server_config(server_name, config)
    tool_cache = cache or ToolCache()

    if not force_refresh:
        cached = tool_cache.get(server_name, server_config)
        if cached is not None:
            return cached

    tools = await _fetch_tools(server_name, server_config)
    tool_cache.put(server_name, server_config, tools)
    return tools


async def _fetch_tools(
    server_name: str,
    server_config,
) -> list[ToolDefinition]:
    """Connect to server and fetch tool definitions."""
    async with connect(server_config) as session:
        result = await session.list_tools()

    tools = []
    for tool in result.tools:
        tools.append(
            ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                server_name=server_name,
            )
        )
    return tools
