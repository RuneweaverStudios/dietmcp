"""dietmcp CLI entry point."""

from __future__ import annotations

import click

from dietmcp import __version__
from dietmcp.cli.config_cmd import config_cmd
from dietmcp.cli.discover import discover_cmd
from dietmcp.cli.exec import exec_cmd
from dietmcp.cli.skills import skills_cmd


@click.group()
@click.version_option(version=__version__, prog_name="dietmcp")
def cli() -> None:
    """dietmcp - MCP-to-CLI bridge for LLM agents.

    Converts MCP server tools into lightweight bash commands,
    reducing context window bloat and enabling efficient tool use.
    """


cli.add_command(discover_cmd)
cli.add_command(exec_cmd)
cli.add_command(skills_cmd)
cli.add_command(config_cmd)


if __name__ == "__main__":
    cli()
