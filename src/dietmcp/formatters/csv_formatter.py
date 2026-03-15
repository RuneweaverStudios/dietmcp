"""CSV-style formatter for tabular MCP responses."""

from __future__ import annotations

import csv
import io
import json

from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult


class CsvFormatter:
    """Formatter that renders tabular data as CSV.

    Falls back to summary-style output if the response
    doesn't contain recognizable tabular data.
    """

    def format(self, result: ToolResult, max_size: int) -> TunedResponse:
        rows = _extract_rows(result)

        if rows is None:
            # Not tabular — fall back to plain text
            text = result.text_content()
            was_truncated = len(text) > max_size
            return TunedResponse(
                format_name="csv",
                content=text[:max_size] if was_truncated else text,
                was_truncated=was_truncated,
            )

        output = io.StringIO()
        if rows:
            headers = list(rows[0].keys())
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        text = output.getvalue()
        was_truncated = len(text) > max_size

        return TunedResponse(
            format_name="csv",
            content=text[:max_size] if was_truncated else text,
            was_truncated=was_truncated,
        )


def _extract_rows(result: ToolResult) -> list[dict] | None:
    """Try to extract a list of dicts from the tool result."""
    text = result.text_content()

    # Try parsing as JSON array of objects
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            if not parsed:
                return []
            if isinstance(parsed[0], dict):
                return parsed
    except (json.JSONDecodeError, IndexError):
        pass

    # Try extracting from raw response
    raw = result.raw
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value

    return None
