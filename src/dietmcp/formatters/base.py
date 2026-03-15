"""Formatter protocol for response post-processing."""

from __future__ import annotations

from typing import Protocol

from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult


class Formatter(Protocol):
    """Protocol for response formatters."""

    def format(self, result: ToolResult, max_size: int) -> TunedResponse:
        """Format a tool result into a compact representation.

        Args:
            result: The raw tool result to format.
            max_size: Maximum character count before truncation.

        Returns:
            A TunedResponse with the formatted content.
        """
        ...
