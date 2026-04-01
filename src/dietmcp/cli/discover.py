"""dietmcp discover - list tools from an MCP server."""

from __future__ import annotations

from pathlib import Path

import click

from dietmcp.cli.common import (
    async_command,
    config_option,
    handle_errors,
    refresh_option,
)
from dietmcp.config.loader import list_server_names, load_config, detect_protocol
from dietmcp.core.discovery import discover_tools


@click.command("discover")
@click.argument("server", required=False)
@config_option
@refresh_option
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON schemas.")
@click.option("--protocol", type=click.Choice(["mcp", "openapi", "graphql"], case_sensitive=False),
              help="Explicit protocol (auto-detected if not specified)")
@handle_errors
@async_command
async def discover_cmd(
    server: str | None,
    config_path: Path | None,
    refresh: bool,
    as_json: bool,
    protocol: str | None,
) -> None:
    """Discover tools from an MCP, OpenAPI, or GraphQL server.

    If no SERVER is specified, lists all configured servers.

    Protocol auto-detection:
    - MCP servers (stdio/SSE): Listed in config.mcpServers
    - OpenAPI (REST): Listed in config.openapiServers
    - GraphQL: Listed in config.graphqlServers

    Use --protocol to override auto-detection or specify protocol for direct URLs.
    """
    config = load_config(config_path)

    if server is None:
        # List configured servers
        names = list_server_names(config)
        if not names:
            click.echo("No servers configured. Run 'dietmcp config init' to get started.")
            return

        click.echo("Configured servers:")
        for name in names:
            proto = detect_protocol(name, config)
            click.echo(f"  {name} ({proto})")
        return

    try:
        tools = await discover_tools(server, config, force_refresh=refresh, protocol=protocol)
    except Exception as exc:
        from dietmcp.config.loader import ConfigError
        if isinstance(exc, ConfigError):
            click.echo(str(exc), err=True)
            import sys
            sys.exit(1)
        raise

    if as_json:
        import json

        schemas = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
        click.echo(json.dumps(schemas, indent=2))
        return

    # Table-style output
    detected_proto = protocol or detect_protocol(server, config)
    click.echo(f"{server} ({detected_proto}): {len(tools)} tools\n")
    for tool in sorted(tools, key=lambda t: t.name):
        desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
        params = tool.parameter_count()
        click.echo(f"  {tool.name:<30} {params} params  {desc}")
