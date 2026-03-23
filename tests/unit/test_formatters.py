"""Tests for response formatters."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dietmcp.formatters.csv_formatter import CsvFormatter
from dietmcp.formatters.file_writer import write_response
from dietmcp.formatters.minified_formatter import MinifiedFormatter
from dietmcp.formatters.registry import get_formatter, list_formatters
from dietmcp.formatters.summary_formatter import SummaryFormatter
from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult


class TestSummaryFormatter:
    def test_short_content(self, text_tool_result):
        fmt = SummaryFormatter()
        result = fmt.format(text_tool_result, max_size=10000)
        assert result.format_name == "summary"
        assert "Hello, world!" in result.content
        assert result.was_truncated is False

    def test_truncated_content(self):
        result = ToolResult(content=[{"type": "text", "text": "x" * 1000}])
        fmt = SummaryFormatter()
        response = fmt.format(result, max_size=100)
        assert response.was_truncated is True
        assert "Truncated" in response.content
        assert "--output-file" in response.content

    def test_error_content(self, error_tool_result):
        fmt = SummaryFormatter()
        result = fmt.format(error_tool_result, max_size=10000)
        assert "[ERROR]" in result.content
        assert result.is_error is True

    def test_error_truncated(self):
        result = ToolResult(
            content=[{"type": "text", "text": "E" * 500}], is_error=True
        )
        fmt = SummaryFormatter()
        response = fmt.format(result, max_size=100)
        assert "[ERROR]" in response.content
        assert response.was_truncated is True
        assert response.is_error is True

    def test_non_error_is_error_false(self, text_tool_result):
        fmt = SummaryFormatter()
        result = fmt.format(text_tool_result, max_size=10000)
        assert result.is_error is False


class TestMinifiedFormatter:
    def test_basic(self, text_tool_result):
        fmt = MinifiedFormatter()
        result = fmt.format(text_tool_result, max_size=10000)
        assert result.format_name == "minified"
        # Should be valid JSON
        parsed = json.loads(result.content)
        assert "content" in parsed

    def test_strips_nulls(self):
        result = ToolResult(
            content=[{"type": "text", "text": "hi"}],
            raw={"data": "hi", "error": None, "meta": None},
        )
        fmt = MinifiedFormatter()
        response = fmt.format(result, max_size=10000)
        parsed = json.loads(response.content)
        assert "error" not in parsed
        assert "meta" not in parsed
        assert parsed["data"] == "hi"

    def test_truncated(self):
        result = ToolResult(
            content=[{"type": "text", "text": "x" * 1000}]
        )
        fmt = MinifiedFormatter()
        response = fmt.format(result, max_size=50)
        assert response.was_truncated is True
        assert len(response.content) == 50

    def test_is_error_propagated(self):
        result = ToolResult(
            content=[{"type": "text", "text": "fail"}], is_error=True
        )
        fmt = MinifiedFormatter()
        response = fmt.format(result, max_size=10000)
        assert response.is_error is True


class TestCsvFormatter:
    def test_tabular_data(self, tabular_tool_result):
        fmt = CsvFormatter()
        result = fmt.format(tabular_tool_result, max_size=10000)
        assert result.format_name == "csv"
        assert "name,size,modified" in result.content
        assert "README.md" in result.content

    def test_non_tabular_fallback(self, text_tool_result):
        fmt = CsvFormatter()
        result = fmt.format(text_tool_result, max_size=10000)
        assert "Hello, world!" in result.content

    def test_empty_rows(self):
        result = ToolResult(content=[{"type": "text", "text": "[]"}])
        fmt = CsvFormatter()
        response = fmt.format(result, max_size=10000)
        # Empty array should produce empty output
        assert response.content == ""

    def test_is_error_propagated_tabular(self):
        data = json.dumps([{"a": 1}])
        result = ToolResult(
            content=[{"type": "text", "text": data}], is_error=True
        )
        fmt = CsvFormatter()
        response = fmt.format(result, max_size=10000)
        assert response.is_error is True

    def test_is_error_propagated_non_tabular(self):
        result = ToolResult(
            content=[{"type": "text", "text": "fail"}], is_error=True
        )
        fmt = CsvFormatter()
        response = fmt.format(result, max_size=10000)
        assert response.is_error is True


class TestFormatterRegistry:
    def test_get_summary(self):
        fmt = get_formatter("summary")
        assert isinstance(fmt, SummaryFormatter)

    def test_get_minified(self):
        fmt = get_formatter("minified")
        assert isinstance(fmt, MinifiedFormatter)

    def test_get_csv(self):
        fmt = get_formatter("csv")
        assert isinstance(fmt, CsvFormatter)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("nonexistent")

    def test_list_formatters(self):
        names = list_formatters()
        assert "summary" in names
        assert "minified" in names
        assert "csv" in names


class TestFileWriter:
    def test_small_content_returns_unchanged(self):
        resp = TunedResponse(format_name="summary", content="small")
        result = write_response(resp, output_path=None, max_stdout_size=1000)
        assert result.output_path is None
        assert result.content == "small"

    def test_output_path_writes_to_file(self, tmp_path):
        resp = TunedResponse(format_name="summary", content="file content")
        out = str(tmp_path / "output.txt")
        result = write_response(resp, output_path=out, max_stdout_size=1000)
        assert result.output_path == out
        assert Path(out).read_text() == "file content"

    def test_large_content_auto_redirects(self):
        large = "x" * 10000
        resp = TunedResponse(format_name="summary", content=large)
        result = write_response(resp, output_path=None, max_stdout_size=1000)
        assert result.output_path is not None
        assert Path(result.output_path).read_text() == large
        # Clean up
        os.unlink(result.output_path)

    def test_display_shows_file_pointer(self, tmp_path):
        resp = TunedResponse(
            format_name="summary",
            content="x" * 500,
            output_path=str(tmp_path / "out.txt"),
        )
        display = resp.display()
        assert "out.txt" in display
        assert "500" in display

    def test_is_error_propagated_to_file(self, tmp_path):
        resp = TunedResponse(format_name="summary", content="error", is_error=True)
        out = str(tmp_path / "err.txt")
        result = write_response(resp, output_path=out, max_stdout_size=1000)
        assert result.is_error is True

    def test_is_error_propagated_on_auto_redirect(self):
        large = "x" * 10000
        resp = TunedResponse(format_name="summary", content=large, is_error=True)
        result = write_response(resp, output_path=None, max_stdout_size=1000)
        assert result.is_error is True
        # Clean up
        os.unlink(result.output_path)
