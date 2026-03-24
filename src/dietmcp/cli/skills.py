"""dietmcp skills - generate compact skill summaries."""

from __future__ import annotations

import os
from pathlib import Path

import click

from dietmcp.cli.common import (
    async_command,
    config_option,
    handle_errors,
    refresh_option,
)
from dietmcp.config.loader import list_server_names, load_config
from dietmcp.core.skills_generator import generate_skills
from dietmcp.security.masking import collect_secret_values, mask_secrets


@click.command("skills")
@click.argument("server", required=False)
@config_option
@refresh_option
@click.option("--all", "all_servers", is_flag=True, help="Generate skills for all servers.")
@handle_errors
@async_command
async def skills_cmd(
    server: str | None,
    config_path: Path | None,
    refresh: bool,
    all_servers: bool,
) -> None:
    """Generate compact skill summaries for LLM context.

    Produces a lightweight description of available tools that uses
    far fewer tokens than full JSON schemas.
    """
    config = load_config(config_path)

    if all_servers:
        names = list_server_names(config)
    elif server:
        names = [server]
    else:
        click.echo("Specify a SERVER name or use --all.", err=True)
        raise SystemExit(1)

    errors = []
    for name in names:
        try:
            summary = await generate_skills(name, config, force_refresh=refresh)
            click.echo(summary.render())
            click.echo()
        except Exception as exc:
            errors.append(name)
            secrets = collect_secret_values(dict(os.environ))
            safe_msg = mask_secrets(str(exc), secrets)
            click.echo(f"# {name}: skipped ({safe_msg})", err=True)

    if errors:
        raise SystemExit(1)
