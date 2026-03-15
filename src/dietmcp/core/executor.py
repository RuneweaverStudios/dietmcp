"""Tool execution against MCP servers.

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
"""

from __future__ import annotations

from dietmcp.cache.tool_cache import ToolCache
from dietmcp.config.loader import DietMcpConfig, get_server_config
from dietmcp.core.discovery import discover_tools
from dietmcp.formatters.base import Formatter
from dietmcp.formatters.file_writer import write_response
from dietmcp.formatters.registry import get_formatter
from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult
from dietmcp.transport.connection import connect


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
) -> TunedResponse:
    """Execute a tool on an MCP server and return formatted output.

    Args:
        server_name: Name of the target server.
        tool_name: Name of the tool to execute.
        arguments: JSON-compatible arguments dict.
        config: Full application configuration.
        output_format: Formatter name (summary, minified, csv).
        output_file: Optional path to write output to file.
        max_response_size: Max chars before auto-redirect to file.
        cache: Optional cache instance.

    Returns:
        TunedResponse with formatted (and possibly file-redirected) content.
    """
    server_config = get_server_config(server_name, config)
    max_size = max_response_size or config.defaults.max_response_size

    # Validate tool exists
    tools = await discover_tools(server_name, config, cache=cache)
    matching = [t for t in tools if t.name == tool_name]
    if not matching:
        available = [t.name for t in tools]
        raise ToolNotFoundError(
            f"Tool '{tool_name}' not found on server '{server_name}'. "
            f"Available: {', '.join(sorted(available))}"
        )

    # Execute
    result = await _call_tool(server_config, tool_name, arguments)

    # Format
    formatter = get_formatter(output_format)
    formatted = formatter.format(result, max_size)

    # File redirect
    return write_response(formatted, output_file, max_size)


async def _call_tool(
    server_config, tool_name: str, arguments: dict
) -> ToolResult:
    """Connect to server and execute a single tool call."""
    async with connect(server_config) as session:
        result = await session.call_tool(tool_name, arguments)

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
