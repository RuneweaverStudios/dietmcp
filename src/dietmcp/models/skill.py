"""Skill summary models for compact LLM-friendly tool descriptions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SkillEntry(BaseModel):
    """A single tool compressed into a one-line description."""

    model_config = ConfigDict(frozen=True)

    signature: str
    description: str

    def render(self) -> str:
        return f"- {self.signature} -- {self.description}"


class SkillCategory(BaseModel):
    """A group of related tools under a category heading."""

    model_config = ConfigDict(frozen=True)

    name: str
    tools: tuple[SkillEntry, ...]

    def render(self) -> str:
        lines = [f"## {self.name}"]
        for tool in self.tools:
            lines.append(tool.render())
        return "\n".join(lines)


class SkillSummary(BaseModel):
    """Complete skill summary for an MCP server."""

    model_config = ConfigDict(frozen=True)

    server_name: str
    tool_count: int
    categories: tuple[SkillCategory, ...]
    exec_syntax: str

    def render(self) -> str:
        lines = [f"# {self.server_name} ({self.tool_count} tools)", ""]
        for category in self.categories:
            lines.append(category.render())
            lines.append("")
        lines.append(f"Exec: {self.exec_syntax}")
        return "\n".join(lines)
