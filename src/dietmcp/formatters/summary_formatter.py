"""Summary formatter: extracts key info, truncates long values."""

from __future__ import annotations

from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult


class SummaryFormatter:
    """Default formatter that produces LLM-friendly summaries."""

    def format(self, result: ToolResult, max_size: int) -> TunedResponse:
        text = result.text_content()
        total_size = len(text)
        was_truncated = False

        if result.is_error:
            content = f"[ERROR] {text[:max_size]}"
            was_truncated = total_size > max_size
        elif total_size <= max_size:
            content = text
        else:
            was_truncated = True
            content = (
                f"{text[:max_size]}\n"
                f"---\n"
                f"[Truncated: {total_size:,} chars total. "
                f"Use --output-file to capture full response.]"
            )

        return TunedResponse(
            format_name="summary",
            content=content,
            is_error=result.is_error,
            was_truncated=was_truncated,
        )
