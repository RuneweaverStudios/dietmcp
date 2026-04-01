"""dietmcp config - manage server configuration."""

from __future__ import annotations

import json
from pathlib import Path

import click

from dietmcp.cli.common import config_option, handle_errors
from dietmcp.config.defaults import CONFIG_FILE
from dietmcp.config.loader import create_default_config, load_config
from dietmcp.security.masking import collect_secret_values, mask_secrets


@click.group("config")
def config_cmd() -> None:
    """Manage dietmcp server configuration."""


@config_cmd.command("show")
@config_option
@handle_errors
def config_show(config_path: Path | None) -> None:
    """Display current configuration with secrets masked."""
    config = load_config(config_path)
    raw = config.model_dump()

    # Collect all env values that look like secrets and mask them
    secret_values = set()

    # MCP servers
    for server in raw.get("mcpServers", {}).values():
        for value in server.get("env", {}).values():
            if not value.startswith("${"):
                secret_values.add(value)
        for value in server.get("headers", {}).values():
            if not value.startswith("${") and not value.startswith("Bearer ${"):
                secret_values.add(value)

    # OpenAPI servers
    for server in raw.get("openapiServers", {}).values():
        auth = server.get("auth", {})
        header = auth.get("header", "")
        if header and not header.startswith("${") and not header.startswith("Bearer ${"):
            secret_values.add(header)

    # GraphQL servers
    for server in raw.get("graphqlServers", {}).values():
        auth = server.get("auth", {})
        header = auth.get("header", "")
        if header and not header.startswith("${") and not header.startswith("Bearer ${"):
            secret_values.add(header)

    output = json.dumps(raw, indent=2)
    output = mask_secrets(output, frozenset(secret_values))
    click.echo(output)


@config_cmd.command("path")
def config_path() -> None:
    """Print the config file path."""
    click.echo(CONFIG_FILE)


@config_cmd.command("init")
@config_option
@handle_errors
def config_init(config_path: Path | None) -> None:
    """Create a default configuration file with example servers."""
    target = config_path or CONFIG_FILE
    if target.is_file():
        click.echo(f"Config already exists: {target}")
        if not click.confirm("Overwrite?"):
            return

    path = create_default_config(target)
    click.echo(f"Created config: {path}")


@config_cmd.command("add")
@click.argument("name")
@click.option("--command", required=True, help="Server command (e.g., 'npx').")
@click.option("--args", "server_args", default="", help="Comma-separated server arguments.")
@config_option
@handle_errors
def config_add(
    name: str,
    command: str,
    server_args: str,
    config_path: Path | None,
) -> None:
    """Add a server to the configuration."""
    path = config_path or CONFIG_FILE
    if not path.is_file():
        click.echo(f"No config found at {path}. Run 'dietmcp config init' first.", err=True)
        raise SystemExit(1)

    raw = json.loads(path.read_text(encoding="utf-8"))
    args_list = [a.strip() for a in server_args.split(",") if a.strip()] if server_args else []

    raw.setdefault("mcpServers", {})[name] = {
        "command": command,
        "args": args_list,
    }

    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Added server '{name}' to {path}")


@config_cmd.command("remove")
@click.argument("name")
@config_option
@handle_errors
def config_remove(name: str, config_path: Path | None) -> None:
    """Remove a server from the configuration."""
    path = config_path or CONFIG_FILE
    if not path.is_file():
        click.echo(f"No config found at {path}.", err=True)
        raise SystemExit(1)

    raw = json.loads(path.read_text(encoding="utf-8"))
    servers = raw.get("mcpServers", {})

    if name not in servers:
        click.echo(f"Server '{name}' not found in config.", err=True)
        raise SystemExit(1)

    del servers[name]
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Removed server '{name}' from {path}")
