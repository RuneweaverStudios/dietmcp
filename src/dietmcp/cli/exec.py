"""dietmcp exec - execute a tool on an MCP server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from dietmcp.cli.common import (
    async_command,
    config_option,
    format_option,
    handle_errors,
    output_file_option,
)
from dietmcp.config.loader import load_config
from dietmcp.core.executor import ExecutionError, ToolNotFoundError, execute_tool


@click.command("exec")
@click.argument("server")
@click.argument("tool")
@click.option("--args", "args_json", default="{}", help="JSON arguments string.")
@config_option
@format_option
@output_file_option
@click.option("--protocol", type=click.Choice(["mcp", "openapi", "graphql"], case_sensitive=False),
              help="Explicit protocol (auto-detected if not specified)")
@handle_errors
@async_command
async def exec_cmd(
    server: str,
    tool: str,
    args_json: str,
    config_path: Path | None,
    output_format: str | None,
    output_file: Path | None,
    protocol: str | None,
) -> None:
    """Execute a tool on an MCP, OpenAPI, or GraphQL server.

    Protocol auto-detection:
    - MCP servers (stdio/SSE): Listed in config.mcpServers
    - OpenAPI (REST): Listed in config.openapiServers
    - GraphQL: Listed in config.graphqlServers

    Example:
        dietmcp exec filesystem read_file --args '{"path": "/tmp/test.txt"}'
        dietmcp exec petstore getPetById --args '{"petId": 1}'
    """
    config = load_config(config_path)
    fmt = output_format or config.defaults.output_format

    # Parse arguments JSON
    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as exc:
        click.echo(f"Invalid JSON in --args: {exc}", err=True)
        sys.exit(1)

    if not isinstance(arguments, dict):
        click.echo("--args must be a JSON object (dict), not an array or scalar.", err=True)
        sys.exit(1)

    try:
        response = await execute_tool(
            server_name=server,
            tool_name=tool,
            arguments=arguments,
            config=config,
            output_format=fmt,
            output_file=str(output_file) if output_file else None,
            protocol=protocol,
        )
    except ToolNotFoundError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    except ExecutionError as exc:
        click.echo(f"Execution error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        from dietmcp.config.loader import ConfigError
        if isinstance(exc, ConfigError):
            click.echo(str(exc), err=True)
            sys.exit(1)
        raise

    click.echo(response.display())
    if response.is_error:
        sys.exit(1)
