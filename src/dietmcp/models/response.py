"""Formatted response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TunedResponse(BaseModel):
    """Immutable post-processed response ready for output."""

    model_config = ConfigDict(frozen=True)

    format_name: str
    content: str
    was_truncated: bool = False
    output_path: str | None = None

    def display(self) -> str:
        """Return the string the agent should see."""
        if self.output_path:
            size = len(self.content)
            return f"[Response written to {self.output_path} ({size:,} chars)]"
        return self.content
