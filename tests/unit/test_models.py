"""Tests for frozen Pydantic models."""

from __future__ import annotations

import pytest

from dietmcp.models.response import TunedResponse
from dietmcp.models.server import ServerConfig
from dietmcp.models.skill import SkillCategory, SkillEntry, SkillSummary
from dietmcp.models.tool import ToolDefinition, ToolResult


class TestToolDefinition:
    def test_create(self):
        tool = ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            server_name="fs",
        )
        assert tool.name == "read_file"
        assert tool.server_name == "fs"

    def test_frozen(self):
        tool = ToolDefinition(
            name="test", description="", input_schema={}, server_name="s"
        )
        with pytest.raises(Exception):
            tool.name = "changed"

    def test_parameter_count(self):
        tool = ToolDefinition(
            name="test",
            description="",
            input_schema={
                "properties": {"a": {}, "b": {}, "c": {}},
            },
            server_name="s",
        )
        assert tool.parameter_count() == 3

    def test_required_and_optional_params(self):
        tool = ToolDefinition(
            name="test",
            description="",
            input_schema={
                "properties": {"a": {}, "b": {}, "c": {}},
                "required": ["a"],
            },
            server_name="s",
        )
        assert tool.required_params() == ["a"]
        assert set(tool.optional_params()) == {"b", "c"}

    def test_compact_signature(self):
        tool = ToolDefinition(
            name="search",
            description="",
            input_schema={
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            server_name="s",
        )
        sig = tool.compact_signature()
        assert "search(" in sig
        assert "query: str" in sig
        assert "?limit: int" in sig

    def test_compact_signature_with_enum(self):
        tool = ToolDefinition(
            name="sort",
            description="",
            input_schema={
                "properties": {
                    "order": {"type": "string", "enum": ["asc", "desc"]},
                },
                "required": ["order"],
            },
            server_name="s",
        )
        sig = tool.compact_signature()
        assert '"asc"' in sig
        assert '"desc"' in sig

    def test_compact_signature_with_array(self):
        tool = ToolDefinition(
            name="batch",
            description="",
            input_schema={
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["items"],
            },
            server_name="s",
        )
        sig = tool.compact_signature()
        assert "list[str]" in sig

    def test_empty_schema(self):
        tool = ToolDefinition(
            name="noop", description="", input_schema={}, server_name="s"
        )
        assert tool.parameter_count() == 0
        assert tool.compact_signature() == "noop()"


class TestToolResult:
    def test_text_content(self):
        result = ToolResult(
            content=[
                {"type": "text", "text": "line1"},
                {"type": "text", "text": "line2"},
            ]
        )
        assert result.text_content() == "line1\nline2"

    def test_text_content_empty(self):
        result = ToolResult(content=[])
        assert result.text_content() == ""

    def test_total_size(self):
        result = ToolResult(content=[{"type": "text", "text": "hello"}])
        assert result.total_size() == 5

    def test_is_error_default(self):
        result = ToolResult(content=[])
        assert result.is_error is False

    def test_frozen(self):
        result = ToolResult(content=[])
        with pytest.raises(Exception):
            result.is_error = True


class TestServerConfig:
    def test_stdio_server(self):
        cfg = ServerConfig(name="fs", command="npx", args=("server",))
        assert cfg.is_stdio is True
        assert cfg.is_sse is False

    def test_sse_server(self):
        cfg = ServerConfig(name="remote", url="https://example.com/sse")
        assert cfg.is_stdio is False
        assert cfg.is_sse is True

    def test_default_cache_ttl(self):
        cfg = ServerConfig(name="test")
        assert cfg.cache_ttl == 3600

    def test_frozen(self):
        cfg = ServerConfig(name="test")
        with pytest.raises(Exception):
            cfg.name = "changed"


class TestSkillModels:
    def test_skill_entry_render(self):
        entry = SkillEntry(signature="read(path: str)", description="Read file")
        assert entry.render() == "- read(path: str) -- Read file"

    def test_skill_category_render(self):
        cat = SkillCategory(
            name="File Ops",
            tools=(SkillEntry(signature="read()", description="Read"),),
        )
        rendered = cat.render()
        assert "## File Ops" in rendered
        assert "- read() -- Read" in rendered

    def test_skill_summary_render(self):
        summary = SkillSummary(
            server_name="fs",
            tool_count=1,
            categories=(
                SkillCategory(
                    name="Tools",
                    tools=(SkillEntry(signature="test()", description="Test"),),
                ),
            ),
            exec_syntax="dietmcp exec fs <tool>",
        )
        rendered = summary.render()
        assert "# fs (1 tools)" in rendered
        assert "## Tools" in rendered
        assert "Exec: dietmcp exec fs <tool>" in rendered


class TestTunedResponse:
    def test_display_with_content(self):
        resp = TunedResponse(format_name="summary", content="hello")
        assert resp.display() == "hello"

    def test_display_with_file(self):
        resp = TunedResponse(
            format_name="summary",
            content="x" * 1000,
            output_path="/tmp/out.txt",
        )
        display = resp.display()
        assert "/tmp/out.txt" in display
        assert "1,000 chars" in display

    def test_frozen(self):
        resp = TunedResponse(format_name="summary", content="")
        with pytest.raises(Exception):
            resp.content = "changed"
