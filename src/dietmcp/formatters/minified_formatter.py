"""Minified JSON formatter: compact, null-stripped output."""

from __future__ import annotations

import json

from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult


class MinifiedFormatter:
    """Formatter that produces compact JSON output."""

    def format(self, result: ToolResult, max_size: int) -> TunedResponse:
        raw = result.raw if result.raw else {"content": result.text_content()}
        cleaned = _strip_nulls(raw)
        text = json.dumps(cleaned, separators=(",", ":"), ensure_ascii=False)

        was_truncated = len(text) > max_size
        if was_truncated:
            text = text[:max_size]

        return TunedResponse(
            format_name="minified",
            content=text,
            was_truncated=was_truncated,
        )


def _strip_nulls(obj: object) -> object:
    """Recursively remove None/null values from dicts."""
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(item) for item in obj]
    return obj
