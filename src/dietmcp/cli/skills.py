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
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["compact", "ultra"], case_sensitive=False),
    default="compact",
    help="Output format: compact (29 tokens/tool) or ultra (13-15 tokens/tool).",
)
@handle_errors
@async_command
async def skills_cmd(
    server: str | None,
    config_path: Path | None,
    refresh: bool,
    all_servers: bool,
    format_type: str,
) -> None:
    """Generate compact skill summaries for LLM context.

    Produces a lightweight description of available tools that uses
    far fewer tokens than full JSON schemas.

    Default format (compact): ~29 tokens/tool
    Ultra format: ~13-15 tokens/tool (best for LLM context)
    """
    config = load_config(config_path)
    ultra_compact = format_type == "ultra"

    if all_servers:
        names = list_server_names(config)
    elif server:
        names = [server]
    else:
        click.echo("Specify a SERVER name or use --all.", err=True)
        raise SystemExit(1)

    import asyncio

    async def _gen(name: str) -> tuple[str, str | None, str | None]:
        try:
            summary = await generate_skills(
                name, config, force_refresh=refresh, ultra_compact=ultra_compact
            )
            return (name, summary.render(), None)
        except Exception as exc:
            secrets = collect_secret_values(dict(os.environ))
            safe_msg = mask_secrets(str(exc), secrets)
            return (name, None, safe_msg)

    results = await asyncio.gather(*[_gen(n) for n in names])

    errors = []
    for name, rendered, err_msg in results:
        if rendered:
            click.echo(rendered)
            click.echo()
        else:
            errors.append(name)
            click.echo(f"# {name}: skipped ({err_msg})", err=True)

    if errors:
        raise SystemExit(1)
