"""Tests for skill summary generation."""

from __future__ import annotations

import pytest

from dietmcp.core.skills_generator import _categorize_tools, _truncate
from dietmcp.models.tool import ToolDefinition, _json_type_to_hint


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


class TestJsonTypeToHint:
    """Test type hint conversion with ultra-compact mode."""

    def test_primitive_string_standard(self):
        schema = {"type": "string"}
        assert _json_type_to_hint(schema, ultra_compact=False) == "str"

    def test_primitive_string_ultra(self):
        """Ultra-compact mode omits primitive types."""
        schema = {"type": "string"}
        assert _json_type_to_hint(schema, ultra_compact=True) == ""

    def test_primitive_int_standard(self):
        schema = {"type": "integer"}
        assert _json_type_to_hint(schema, ultra_compact=False) == "int"

    def test_primitive_int_ultra(self):
        schema = {"type": "integer"}
        assert _json_type_to_hint(schema, ultra_compact=True) == ""

    def test_primitive_bool_ultra(self):
        schema = {"type": "boolean"}
        assert _json_type_to_hint(schema, ultra_compact=True) == ""

    def test_primitive_float_ultra(self):
        schema = {"type": "number"}
        assert _json_type_to_hint(schema, ultra_compact=True) == ""

    def test_array_of_strings_standard(self):
        schema = {"type": "array", "items": {"type": "string"}}
        assert _json_type_to_hint(schema, ultra_compact=False) == "list[str]"

    def test_array_of_strings_ultra(self):
        schema = {"type": "array", "items": {"type": "string"}}
        assert _json_type_to_hint(schema, ultra_compact=True) == "[str]"

    def test_array_of_ints_ultra(self):
        schema = {"type": "array", "items": {"type": "integer"}}
        assert _json_type_to_hint(schema, ultra_compact=True) == "[int]"

    def test_enum_values_standard(self):
        schema = {"type": "string", "enum": ["json", "yaml", "xml"]}
        result = _json_type_to_hint(schema, ultra_compact=False)
        assert '"json"' in result
        assert '"yaml"' in result
        assert '"xml"' in result

    def test_enum_values_ultra(self):
        """Enums show values in both modes."""
        schema = {"type": "string", "enum": ["json", "yaml", "xml"]}
        result = _json_type_to_hint(schema, ultra_compact=True)
        assert '"json"' in result
        assert '"yaml"' in result
        assert '"xml"' in result

    def test_object_type_ultra(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
        }
        result = _json_type_to_hint(schema, ultra_compact=True)
        assert "{" in result
        assert "name" in result
        assert "email" in result

    def test_empty_object_ultra(self):
        schema = {"type": "object"}
        assert _json_type_to_hint(schema, ultra_compact=True) == "{}"

    def test_array_of_objects_ultra(self):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            },
        }
        result = _json_type_to_hint(schema, ultra_compact=True)
        assert result == "[{id, name}]"


class TestCompactSignature:
    """Test ToolDefinition.compact_signature() with ultra-compact mode."""

    def test_standard_format(self):
        tool = ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer"},
                },
                "required": ["path"],
            },
            server_name="test",
        )
        result = tool.compact_signature(ultra_compact=False)
        assert result == "read_file(path: str, ?offset: int)"

    def test_ultra_compact_format_primitives(self):
        """Ultra-compact omits primitive types."""
        tool = ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer"},
                },
                "required": ["path"],
            },
            server_name="test",
        )
        result = tool.compact_signature(ultra_compact=True)
        assert result == "read_file(path, offset?)"

    def test_ultra_compact_with_array_param(self):
        """Ultra-compact preserves complex types."""
        tool = ToolDefinition(
            name="search_files",
            description="Search files",
            input_schema={
                "properties": {
                    "path": {"type": "string"},
                    "patterns": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["path", "patterns"],
            },
            server_name="test",
        )
        result = tool.compact_signature(ultra_compact=True)
        assert result == "search_files(path, patterns: [str])"

    def test_ultra_compact_with_enum_param(self):
        """Ultra-compact preserves enum values."""
        tool = ToolDefinition(
            name="format_data",
            description="Format data",
            input_schema={
                "properties": {
                    "data": {"type": "string"},
                    "format": {"type": "string", "enum": ["json", "yaml", "xml"]},
                },
                "required": ["data", "format"],
            },
            server_name="test",
        )
        result = tool.compact_signature(ultra_compact=True)
        assert 'format: "json" | "yaml" | "xml"' in result

    def test_ultra_compact_optional_complex_type(self):
        """Optional complex type in ultra-compact format."""
        tool = ToolDefinition(
            name="process_items",
            description="Process items",
            input_schema={
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [],
            },
            server_name="test",
        )
        result = tool.compact_signature(ultra_compact=True)
        assert result == "process_items(items?: [str])"

    def test_standard_format_description_truncation(self):
        """Standard format truncates at 80 chars."""
        from dietmcp.core.skills_generator import _truncate
        long_desc = "This is a very long description that exceeds the maximum allowed length and should be truncated"
        result = _truncate(long_desc, 80)
        assert len(result) <= 80
        assert result.endswith("...")

    def test_ultra_compact_description_truncation(self):
        """Ultra-compact format truncates at 40 chars."""
        long_desc = "This is a very long description that should be truncated"
        result = _truncate(long_desc, 40)
        assert len(result) <= 40
        assert result.endswith("...")
