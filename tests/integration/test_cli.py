"""Integration tests for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dietmcp.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    config = {
        "mcpServers": {
            "test-server": {
                "command": "echo",
                "args": ["hello"],
            }
        },
        "defaults": {
            "cacheTtlSeconds": 3600,
            "outputFormat": "summary",
            "maxResponseSize": 50000,
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return path


class TestVersionCommand:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestConfigCommands:
    def test_config_path(self, runner):
        result = runner.invoke(cli, ["config", "path"])
        assert result.exit_code == 0
        assert "servers.json" in result.output

    def test_config_init(self, runner, tmp_path):
        path = str(tmp_path / "test_config.json")
        result = runner.invoke(cli, ["config", "init", "--config", path])
        assert result.exit_code == 0
        assert Path(path).is_file()
        data = json.loads(Path(path).read_text())
        assert "mcpServers" in data

    def test_config_show(self, runner, config_file):
        result = runner.invoke(cli, ["config", "show", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "test-server" in result.output

    def test_config_add(self, runner, config_file):
        result = runner.invoke(
            cli,
            [
                "config", "add", "new-server",
                "--command", "python",
                "--args", "-m,mcp_server",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "new-server" in data["mcpServers"]

    def test_config_remove(self, runner, config_file):
        result = runner.invoke(
            cli,
            ["config", "remove", "test-server", "--config", str(config_file)],
        )
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "test-server" not in data["mcpServers"]

    def test_config_remove_nonexistent(self, runner, config_file):
        result = runner.invoke(
            cli,
            ["config", "remove", "nope", "--config", str(config_file)],
        )
        assert result.exit_code != 0


class TestDiscoverCommand:
    def test_discover_no_server_lists_all(self, runner, config_file):
        result = runner.invoke(
            cli, ["discover", "--config", str(config_file)]
        )
        assert result.exit_code == 0
        assert "test-server" in result.output

    def test_discover_missing_config(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            ["discover", "--config", str(tmp_path / "nonexistent.json")],
        )
        assert result.exit_code != 0


class TestExecCommand:
    def test_exec_invalid_json_args(self, runner, config_file):
        result = runner.invoke(
            cli,
            [
                "exec", "test-server", "some_tool",
                "--args", "not json",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_exec_non_dict_args(self, runner, config_file):
        result = runner.invoke(
            cli,
            [
                "exec", "test-server", "some_tool",
                "--args", '"just a string"',
                "--config", str(config_file),
            ],
        )
        assert result.exit_code != 0
        assert "JSON object" in result.output


class TestSkillsCommand:
    def test_skills_no_args(self, runner, config_file):
        result = runner.invoke(
            cli, ["skills", "--config", str(config_file)]
        )
        # Should fail because no server or --all specified
        assert result.exit_code != 0
