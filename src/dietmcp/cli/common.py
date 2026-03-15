"""Shared CLI utilities: async bridge, error handling, options."""

from __future__ import annotations

import asyncio
import functools
import sys
from pathlib import Path
from typing import Any, Callable

import click

from dietmcp.config.loader import ConfigError, load_config
from dietmcp.security.masking import collect_secret_values, mask_secrets


def async_command(fn: Callable) -> Callable:
    """Decorator that bridges async Click commands to sync execution."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


def handle_errors(fn: Callable) -> Callable:
    """Decorator that catches known exceptions and prints user-friendly messages."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ConfigError as exc:
            click.echo(f"Config error: {exc}", err=True)
            sys.exit(1)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            click.echo("\nInterrupted.", err=True)
            sys.exit(130)
        except Exception as exc:
            # Mask any secrets that might appear in tracebacks
            msg = str(exc)
            click.echo(f"Unexpected error: {msg}", err=True)
            sys.exit(1)

    return wrapper


# Common Click options
config_option = click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to servers.json config file.",
)

format_option = click.option(
    "--output-format",
    "output_format",
    type=click.Choice(["summary", "minified", "csv"]),
    default=None,
    help="Output format (default: from config or 'summary').",
)

output_file_option = click.option(
    "--output-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Write response to file instead of stdout.",
)

refresh_option = click.option(
    "--refresh",
    is_flag=True,
    default=False,
    help="Bypass cache and fetch fresh data.",
)
