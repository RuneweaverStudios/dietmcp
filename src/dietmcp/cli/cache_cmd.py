"""dietmcp cache - manage the tool schema cache."""

from __future__ import annotations

import click

from dietmcp.cache.tool_cache import ToolCache
from dietmcp.config.defaults import CACHE_DIR


@click.group("cache")
def cache_cmd() -> None:
    """Manage the tool schema cache."""


@cache_cmd.command("clear")
def cache_clear() -> None:
    """Remove all cached tool schemas."""
    cache = ToolCache()
    cache.invalidate_all()
    click.echo("Cache cleared.")


@cache_cmd.command("path")
def cache_path() -> None:
    """Print the cache directory path."""
    click.echo(CACHE_DIR)


@cache_cmd.command("list")
def cache_list() -> None:
    """List cached server schemas."""
    if not CACHE_DIR.is_dir():
        click.echo("Cache is empty.")
        return

    files = sorted(CACHE_DIR.glob("*.json"))
    if not files:
        click.echo("Cache is empty.")
        return

    import json

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            name = data.get("server_name", "unknown")
            tool_count = len(data.get("tools", []))
            cached_at = data.get("cached_at", "unknown")
            click.echo(f"  {name:<20} {tool_count} tools  cached {cached_at}")
        except (json.JSONDecodeError, OSError):
            click.echo(f"  {f.name:<20} (corrupted)")
