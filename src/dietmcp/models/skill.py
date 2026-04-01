"""Skill summary models for compact LLM-friendly tool descriptions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SkillEntry(BaseModel):
    """A single tool compressed into a one-line description."""

    model_config = ConfigDict(frozen=True)

    signature: str
    description: str
    ultra_compact: bool = False

    def render(self) -> str:
        if self.ultra_compact:
            # Ultra-compact: no bullet, no dashes, just signature + description
            return f"{self.signature} {self.description}"
        else:
            # Standard compact: bullet + dashes
            return f"- {self.signature} -- {self.description}"


class SkillCategory(BaseModel):
    """A group of related tools under a category heading."""

    model_config = ConfigDict(frozen=True)

    name: str
    tools: tuple[SkillEntry, ...]
    ultra_compact: bool = False

    def render(self) -> str:
        lines = [f"## {self.name}"]
        for tool in self.tools:
            # Update tool's ultra_compact flag before rendering
            tool_with_flag = tool.model_copy(update={"ultra_compact": self.ultra_compact})
            lines.append(tool_with_flag.render())
        return "\n".join(lines)


class SkillSummary(BaseModel):
    """Complete skill summary for an MCP server."""

    model_config = ConfigDict(frozen=True)

    server_name: str
    tool_count: int
    categories: tuple[SkillCategory, ...]
    exec_syntax: str
    ultra_compact: bool = False

    def render(self) -> str:
        lines = [f"# {self.server_name} ({self.tool_count} tools)", ""]
        for category in self.categories:
            # Update category's ultra_compact flag before rendering
            cat_with_flag = category.model_copy(update={"ultra_compact": self.ultra_compact})
            lines.append(cat_with_flag.render())
            lines.append("")
        lines.append(f"Exec: {self.exec_syntax}")
        return "\n".join(lines)
