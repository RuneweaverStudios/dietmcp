"""Tests for cli/cache_cmd.py — cache management commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from dietmcp.cli.cache_cmd import cache_cmd


class TestCacheClear:
    def test_clear_removes_files(self, tmp_path):
        cache_file = tmp_path / "abc123.json"
        cache_file.write_text("{}")

        from unittest.mock import patch

        with patch("dietmcp.cli.cache_cmd.ToolCache") as mock_cls:
            mock_instance = mock_cls.return_value
            runner = CliRunner()
            result = runner.invoke(cache_cmd, ["clear"])

        assert result.exit_code == 0
        assert "cleared" in result.output.lower()


class TestCachePath:
    def test_prints_path(self):
        runner = CliRunner()
        result = runner.invoke(cache_cmd, ["path"])
        assert result.exit_code == 0
        assert "dietmcp" in result.output


class TestCacheList:
    def test_empty_cache(self, tmp_path):
        from unittest.mock import patch

        with patch("dietmcp.cli.cache_cmd.CACHE_DIR", tmp_path):
            runner = CliRunner()
            result = runner.invoke(cache_cmd, ["list"])

        assert "empty" in result.output.lower()

    def test_lists_cached_servers(self, tmp_path):
        cache_data = {
            "server_name": "filesystem",
            "tools": [{"name": "t1"}, {"name": "t2"}],
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        (tmp_path / "abc.json").write_text(json.dumps(cache_data))

        from unittest.mock import patch

        with patch("dietmcp.cli.cache_cmd.CACHE_DIR", tmp_path):
            runner = CliRunner()
            result = runner.invoke(cache_cmd, ["list"])

        assert "filesystem" in result.output
        assert "2 tools" in result.output
