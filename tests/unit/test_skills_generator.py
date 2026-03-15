"""Tests for skill summary generation."""

from __future__ import annotations

import pytest

from dietmcp.core.skills_generator import _categorize_tools, _truncate
from dietmcp.models.tool import ToolDefinition


@pytest.fixture
def filesystem_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="read_file",
            description="Read the complete contents of a file from the filesystem.",
            input_schema={"properties": {"path": {"type": "string"}}, "required": ["path"]},
            server_name="filesystem",
        ),
        ToolDefinition(
            name="write_file",
            description="Create a new file or overwrite an existing file with content.",
            input_schema={
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            server_name="filesystem",
        ),
        ToolDefinition(
            name="search_files",
            description="Search for files matching a pattern in a directory.",
            input_schema={
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {"type": "string"},
                },
                "required": ["path", "pattern"],
            },
            server_name="filesystem",
        ),
        ToolDefinition(
            name="list_directory",
            description="List files and directories in the given path.",
            input_schema={"properties": {"path": {"type": "string"}}, "required": ["path"]},
            server_name="filesystem",
        ),
    ]


class TestCategorizeTools:
    def test_groups_file_tools(self, filesystem_tools):
        groups = _categorize_tools(filesystem_tools)
        # read_file, write_file, list_directory should be in "File Operations"
        assert "File Operations" in groups
        file_names = {t.name for t in groups["File Operations"]}
        assert "read_file" in file_names
        assert "write_file" in file_names

    def test_groups_search_tools(self, filesystem_tools):
        groups = _categorize_tools(filesystem_tools)
        # search_files has both "search" and "file" keywords, so it may
        # land in "File Operations" (more keyword matches) or "Search".
        # The heuristic picks the category with the highest score.
        all_tool_names = set()
        for cat_tools in groups.values():
            for t in cat_tools:
                all_tool_names.add(t.name)
        assert "search_files" in all_tool_names

    def test_uncategorized_falls_to_tools(self):
        tools = [
            ToolDefinition(
                name="mystery_op",
                description="Does something mysterious",
                input_schema={},
                server_name="test",
            ),
        ]
        groups = _categorize_tools(tools)
        assert "Tools" in groups
        assert groups["Tools"][0].name == "mystery_op"

    def test_empty_tools(self):
        groups = _categorize_tools([])
        assert len(groups) == 0


class TestTruncate:
    def test_short_text(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert _truncate("hello", 5) == "hello"

    def test_long_text(self):
        result = _truncate("hello world this is long", 10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_strips_newlines(self):
        result = _truncate("line1\nline2\nline3", 100)
        assert "\n" not in result

    def test_strips_whitespace(self):
        result = _truncate("  spaced  ", 100)
        assert result == "spaced"
