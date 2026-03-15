"""Formatter registry for selecting formatters by name."""

from __future__ import annotations

from typing import Any

from dietmcp.formatters.base import Formatter
from dietmcp.formatters.csv_formatter import CsvFormatter
from dietmcp.formatters.minified_formatter import MinifiedFormatter
from dietmcp.formatters.summary_formatter import SummaryFormatter


_FORMATTERS: dict[str, Formatter] = {
    "summary": SummaryFormatter(),
    "minified": MinifiedFormatter(),
    "csv": CsvFormatter(),
}


def get_formatter(name: str) -> Formatter:
    """Look up a formatter by name.

    Raises:
        ValueError: If the formatter name is not registered.
    """
    formatter = _FORMATTERS.get(name)
    if formatter is None:
        available = ", ".join(sorted(_FORMATTERS.keys()))
        raise ValueError(
            f"Unknown format '{name}'. Available: {available}"
        )
    return formatter


def list_formatters() -> list[str]:
    """Return sorted list of available formatter names."""
    return sorted(_FORMATTERS.keys())
