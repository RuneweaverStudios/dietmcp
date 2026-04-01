"""Tool discovery from MCP, OpenAPI, and GraphQL servers.

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
- Protocol detection: Auto-detects protocol from server name in config, or
  accepts explicit protocol parameter for direct URL access.
"""

from __future__ import annotations

from dietmcp.cache.tool_cache import ToolCache
from dietmcp.config.loader import DietMcpConfig, detect_protocol, get_server_config
from dietmcp.models.tool import ToolDefinition
from dietmcp.transport.connection import connect


async def discover_tools(
    server_name: str,
    config: DietMcpConfig,
    force_refresh: bool = False,
    cache: ToolCache | None = None,
    protocol: str | None = None,
) -> list[ToolDefinition]:
    """Discover available tools from an MCP, OpenAPI, or GraphQL server.

    Checks the cache first unless force_refresh is True. On cache miss,
    connects to the server, fetches tools, and populates the cache.

    Args:
        server_name: Name of the server as defined in config, or direct URL.
        config: Full application configuration.
        force_refresh: If True, bypass cache and fetch fresh.
        cache: Optional cache instance (uses default if None).
        protocol: Explicit protocol ("mcp", "openapi", "graphql"). If None,
                 auto-detects from server name in config.

    Returns:
        List of ToolDefinition models.

    Raises:
        ConfigError: If server not found or protocol detection fails.
    """
    # Detect protocol if not explicitly provided
    if protocol is None:
        protocol = detect_protocol(server_name, config)

    # Route to appropriate discovery handler
    if protocol == "mcp":
        return await _discover_mcp_tools(server_name, config, force_refresh, cache)
    elif protocol == "openapi":
        return await _discover_openapi_tools(server_name, config, force_refresh, cache)
    elif protocol == "graphql":
        return await _discover_graphql_tools(server_name, config, force_refresh, cache)
    else:
        from dietmcp.config.loader import ConfigError
        raise ConfigError(
            f"Unknown protocol: '{protocol}'. "
            f"Supported: mcp, openapi, graphql"
        )


async def _discover_mcp_tools(
    server_name: str,
    config: DietMcpConfig,
    force_refresh: bool = False,
    cache: ToolCache | None = None,
) -> list[ToolDefinition]:
    """Discover tools from an MCP server."""
    server_config = get_server_config(server_name, config)
    tool_cache = cache or ToolCache()

    if not force_refresh:
        cached = tool_cache.get(server_name, server_config)
        if cached is not None:
            return cached

    tools = await _fetch_mcp_tools(server_name, server_config)
    tool_cache.put(server_name, server_config, tools)
    return tools


async def _fetch_mcp_tools(
    server_name: str,
    server_config,
) -> list[ToolDefinition]:
    """Connect to MCP server and fetch tool definitions."""
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


async def _discover_openapi_tools(
    server_name: str,
    config: DietMcpConfig,
    force_refresh: bool = False,
    cache: ToolCache | None = None,
) -> list[ToolDefinition]:
    """Discover tools from an OpenAPI server.

    Converts OpenAPI endpoints to tool definitions using OpenAPIToolGenerator.
    """
    from dietmcp.openapi.parser import OpenAPIParser
    from dietmcp.openapi.generator import OpenAPIToolGenerator
    from dietmcp.config.schema import OpenAPIServerConfig
    from dietmcp.models.server import ServerConfig
    import httpx

    server_config = config.openapiServers.get(server_name)
    if server_config is None:
        from dietmcp.config.loader import ConfigError
        raise ConfigError(f"OpenAPI server '{server_name}' not found in config")

    # Create a mock ServerConfig for caching
    cache_config = ServerConfig(
        name=f"openapi_{server_name}",
        command=None,
        args=(),
        env={},
        headers={},
        url=server_config.url,
        cache_ttl=server_config.cacheTtl or config.defaults.cache_ttl_seconds,
    )

    tool_cache = cache or ToolCache()

    # Check cache first
    if not force_refresh:
        cached = tool_cache.get(server_name, cache_config)
        if cached is not None:
            return cached

    # Fetch OpenAPI spec
    headers = {}
    if server_config.auth and server_config.auth.header:
        # Parse header string "Authorization: Bearer ${TOKEN}"
        parts = server_config.auth.header.split(":", 1)
        if len(parts) == 2:
            headers[parts[0].strip()] = parts[1].strip()

    async with httpx.AsyncClient() as client:
        response = await client.get(server_config.url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        spec_data = response.json()

    # Parse OpenAPI spec
    parser = OpenAPIParser()
    try:
        spec = parser.parse_spec(spec_data)
    except Exception as e:
        from dietmcp.openapi.parser import OpenAPIParserError
        raise OpenAPIParserError(f"Failed to parse OpenAPI spec: {e}")

    # Convert endpoints to tool definitions using generator
    generator = OpenAPIToolGenerator()
    tools = generator.generate_tools(spec, server_name)

    # Cache using the ServerConfig
    tool_cache.put(server_name, cache_config, tools)
    return tools


async def _discover_graphql_tools(
    server_name: str,
    config: DietMcpConfig,
    force_refresh: bool = False,
    cache: ToolCache | None = None,
) -> list[ToolDefinition]:
    """Discover tools from a GraphQL server.

    Converts GraphQL queries/mutations to tool definitions using GraphQLQueryGenerator.
    """
    from dietmcp.graphql.introspection import GraphQLIntrospector
    from dietmcp.config.schema import GraphQLServerConfig
    from dietmcp.models.server import ServerConfig
    import httpx

    server_config = config.graphqlServers.get(server_name)
    if server_config is None:
        from dietmcp.config.loader import ConfigError
        raise ConfigError(f"GraphQL server '{server_name}' not found in config")

    # Create a mock ServerConfig for caching
    cache_config = ServerConfig(
        name=f"graphql_{server_name}",
        command=None,
        args=(),
        env={},
        headers={},
        url=server_config.url,
        cache_ttl=server_config.cacheTtl or config.defaults.cache_ttl_seconds,
    )

    tool_cache = cache or ToolCache()

    # Check cache first
    if not force_refresh:
        cached = tool_cache.get(server_name, cache_config)
        if cached is not None:
            return cached

    # Prepare headers with auth
    headers = {"Content-Type": "application/json"}
    if server_config.auth and server_config.auth.header:
        parts = server_config.auth.header.split(":", 1)
        if len(parts) == 2:
            headers[parts[0].strip()] = parts[1].strip()

    # Introspect GraphQL schema
    introspector = GraphQLIntrospector(server_config.url, headers)
    schema = await introspector.introspect()

    # Convert queries/mutations to tool definitions using generator
    from dietmcp.graphql import GraphQLQueryGenerator
    generator = GraphQLQueryGenerator(schema)
    tools = generator.generate_tools()

    # Cache
    tool_cache.put(server_name, cache_config, tools)
    return tools


def _endpoint_to_tool(endpoint, server_name: str, base_url: str | None) -> ToolDefinition:
    """Convert an OpenAPI endpoint to a ToolDefinition."""
    from dietmcp.models.openapi import OpenAPIEndpoint

    # Use operation_id as tool name, fallback to method:path
    tool_name = endpoint.operation_id or f"{endpoint.method.lower()}_{endpoint.path.replace('/', '_').replace('{', '').replace('}', '').lstrip('_')}"

    # Build description
    desc_parts = []
    if endpoint.summary:
        desc_parts.append(endpoint.summary)
    elif endpoint.description:
        desc_parts.append(endpoint.description.split("\n")[0])  # First line only

    desc_parts.append(f"{endpoint.method.upper()} {endpoint.path}")
    description = " - ".join(desc_parts)

    # Build JSON schema for parameters
    properties = {}
    required = []

    # Add path parameters
    for param in endpoint.parameters:
        if param.in_ == "path":
            required.append(param.name)
        elif param.required:
            required.append(param.name)

        prop_schema = param.schema_ or {"type": "string"}
        if param.description:
            prop_schema["description"] = param.description
        if param.example is not None:
            prop_schema["example"] = param.example

        properties[param.name] = prop_schema

    # Add request body if present
    if endpoint.request_body:
        # Extract schema from request body
        content = endpoint.request_body.get("content", {})
        if "application/json" in content:
            body_schema = content["application/json"].get("schema", {})
            if "properties" in body_schema:
                properties.update(body_schema["properties"])
            if "required" in body_schema:
                required.extend(body_schema["required"])

    input_schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    return ToolDefinition(
        name=tool_name,
        description=description,
        input_schema=input_schema,
        server_name=server_name,
    )


