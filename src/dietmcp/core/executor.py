"""Tool execution against MCP, OpenAPI, and GraphQL servers.

DEV NOTES:
- The executor opens a SECOND connection to the server (separate from discovery).
  This is intentional: we want discovery to be cached independently, and the
  execution connection to be fresh. A future optimization could reuse the
  discovery connection if cache was missed on the same call.
- Content block handling (lines 80-87) uses hasattr() checks because the MCP SDK
  returns different content types (TextContent, ImageContent, etc.) as a union.
  We normalize everything to dicts for our ToolResult model.
- Binary content is truncated to 200 chars in the preview. The full binary is
  only accessible via --output-file. This prevents base64 blobs from flooding
  the LLM's context window.
- Protocol routing: Auto-detects protocol from server name and routes to
  appropriate executor (MCP, OpenAPI HTTP, or GraphQL HTTP).
"""

from __future__ import annotations

import asyncio
import json

import httpx

from dietmcp.cache.schema_cache import SchemaCache
from dietmcp.cache.tool_cache import ToolCache
from dietmcp.config.loader import DietMcpConfig, detect_protocol, get_server_config
from dietmcp.core.discovery import discover_tools
from dietmcp.formatters.base import Formatter
from dietmcp.formatters.file_writer import write_response
from dietmcp.formatters.registry import get_formatter
from dietmcp.models.response import TunedResponse
from dietmcp.models.server import ServerConfig
from dietmcp.models.tool import ToolResult
from dietmcp.transport.connection import connect


# Module-level schema cache
_schema_cache = SchemaCache()


class ToolNotFoundError(Exception):
    """Raised when a requested tool doesn't exist on the server."""


class ExecutionError(Exception):
    """Raised when tool execution fails."""


async def execute_tool(
    server_name: str,
    tool_name: str,
    arguments: dict,
    config: DietMcpConfig,
    output_format: str = "summary",
    output_file: str | None = None,
    max_response_size: int | None = None,
    cache: ToolCache | None = None,
    protocol: str | None = None,
) -> TunedResponse:
    """Execute a tool on an MCP, OpenAPI, or GraphQL server and return formatted output.

    Args:
        server_name: Name of the target server.
        tool_name: Name of the tool to execute.
        arguments: JSON-compatible arguments dict.
        config: Full application configuration.
        output_format: Formatter name (summary, minified, csv).
        output_file: Optional path to write output to file.
        max_response_size: Max chars before auto-redirect to file.
        cache: Optional cache instance.
        protocol: Explicit protocol ("mcp", "openapi", "graphql"). If None,
                 auto-detects from server name in config.

    Returns:
        TunedResponse with formatted (and possibly file-redirected) content.
    """
    # Detect protocol if not explicitly provided
    if protocol is None:
        protocol = detect_protocol(server_name, config)

    max_size = max_response_size or config.defaults.max_response_size

    # Validate tool exists
    tools = await discover_tools(server_name, config, cache=cache, protocol=protocol)
    matching = [t for t in tools if t.name == tool_name]
    if not matching:
        available = [t.name for t in tools]
        raise ToolNotFoundError(
            f"Tool '{tool_name}' not found on server '{server_name}'. "
            f"Available: {', '.join(sorted(available))}"
        )

    # Route to appropriate executor
    if protocol == "mcp":
        server_config = get_server_config(server_name, config)
        result = await _call_mcp_tool(server_config, tool_name, arguments)
    elif protocol == "openapi":
        result = await _call_openapi_tool(server_name, tool_name, arguments, config)
    elif protocol == "graphql":
        result = await _call_graphql_tool(server_name, tool_name, arguments, config)
    else:
        from dietmcp.config.loader import ConfigError
        raise ConfigError(f"Unknown protocol: '{protocol}'")

    # Format
    formatter = get_formatter(output_format)
    formatted = formatter.format(result, max_size)

    # File redirect
    return write_response(formatted, output_file, max_size)


async def _call_mcp_tool(
    server_config: ServerConfig,
    tool_name: str,
    arguments: dict,
    timeout: float = 30.0,
) -> ToolResult:
    """Connect to MCP server and execute a single tool call."""
    async with connect(server_config) as session:
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise ExecutionError(
                f"Tool '{tool_name}' timed out after {timeout}s. "
                f"The MCP server may be unresponsive."
            )

    content_blocks = []
    for item in result.content:
        if hasattr(item, "text"):
            content_blocks.append({"type": "text", "text": item.text})
        elif hasattr(item, "data"):
            content_blocks.append({"type": "binary", "data": str(item.data)[:200]})
        else:
            content_blocks.append({"type": "unknown", "text": str(item)})

    return ToolResult(
        content=content_blocks,
        is_error=result.isError if hasattr(result, "isError") else False,
    )


async def _call_openapi_tool(
    server_name: str,
    tool_name: str,
    arguments: dict,
    config: DietMcpConfig,
) -> ToolResult:
    """Execute an OpenAPI endpoint as a tool call."""
    from dietmcp.config.schema import OpenAPIServerConfig
    from dietmcp.openapi.executor import OpenAPIExecutor, OpenAPIExecutorError
    from dietmcp.openapi.parser import OpenAPIParser

    server_config = config.openapiServers.get(server_name)
    if server_config is None:
        from dietmcp.config.loader import ConfigError
        raise ConfigError(f"OpenAPI server '{server_name}' not found in config")

    # Fetch and parse OpenAPI spec
    headers = {}
    if server_config.auth and server_config.auth.header:
        parts = server_config.auth.header.split(":", 1)
        if len(parts) == 2:
            headers[parts[0].strip()] = parts[1].strip()

    async with httpx.AsyncClient() as client:
        # Fetch spec
        response = await client.get(server_config.url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        spec_data = response.json()

    # Parse spec
    parser = OpenAPIParser()
    spec = parser.parse_spec(spec_data)

    # Find endpoint by operation_id
    endpoint = spec.get_endpoint_by_id(tool_name)
    if not endpoint:
        raise ToolNotFoundError(f"Tool '{tool_name}' not found on OpenAPI server '{server_name}'")

    # Execute request using OpenAPIExecutor
    async with OpenAPIExecutor(server_config, spec) as executor:
        try:
            result = await executor.execute(endpoint, arguments)
            return result
        except OpenAPIExecutorError as e:
            # Convert executor error to ToolResult with error flag
            return ToolResult(
                content=[{"type": "text", "text": str(e)}],
                is_error=True,
            )


async def _call_graphql_tool(
    server_name: str,
    tool_name: str,
    arguments: dict,
    config: DietMcpConfig,
) -> ToolResult:
    """Execute a GraphQL query/mutation as a tool call."""
    from dietmcp.config.schema import GraphQLServerConfig
    from dietmcp.graphql.executor import GraphQLExecutor
    from dietmcp.graphql.introspection import GraphQLIntrospector

    server_config = config.graphqlServers.get(server_name)
    if server_config is None:
        from dietmcp.config.loader import ConfigError
        raise ConfigError(f"GraphQL server '{server_name}' not found in config")

    # Discover tools to find the operation
    tools = await discover_tools(server_name, config, protocol="graphql")
    tool = next((t for t in tools if t.name == tool_name), None)
    if not tool:
        raise ToolNotFoundError(f"Tool '{tool_name}' not found on GraphQL server '{server_name}'")

    # Introspect schema to get operation details (with caching)
    introspector = GraphQLIntrospector()
    headers = {}
    if server_config.auth and server_config.auth.header:
        parts = server_config.auth.header.split(":", 1)
        if len(parts) == 2:
            headers[parts[0].strip()] = parts[1].strip()

    # Check cache first
    cache_key = f"graphql_schema_{server_config.url}"
    cached_schema = _schema_cache.get(cache_key)

    if cached_schema:
        schema = cached_schema
    else:
        # Introspect and cache
        try:
            schema = await introspector.introspect(server_config.url, headers)
            _schema_cache.put(cache_key, schema)
        except Exception as e:
            raise ExecutionError(f"Failed to introspect GraphQL schema: {e}")

    # Find the operation in the schema
    operation = None
    for query in schema.queries:
        if query.name == tool_name:
            operation = query
            break

    if not operation:
        for mutation in schema.mutations:
            if mutation.name == tool_name:
                operation = mutation
                break

    if not operation:
        raise ToolNotFoundError(
            f"Operation '{tool_name}' not found in GraphQL schema"
        )

    # Execute using GraphQLExecutor
    executor = GraphQLExecutor(server_config)
    try:
        result = await executor.execute(operation, arguments, schema)
        return result
    except Exception as e:
        raise ExecutionError(f"GraphQL execution failed: {e}")
