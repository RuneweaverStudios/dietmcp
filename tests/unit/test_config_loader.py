"""Tests for configuration loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dietmcp.config.loader import (
    ConfigError,
    create_default_config,
    get_server_config,
    list_server_names,
    load_config,
    resolve_server,
)
from dietmcp.config.schema import DietMcpConfig, ServerEntry


class TestLoadConfig:
    def test_valid_config(self, sample_config_path):
        config = load_config(sample_config_path)
        assert "filesystem" in config.mcpServers
        assert "github" in config.mcpServers

    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.json")

    def test_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        with pytest.raises(ConfigError, match="Invalid JSON"):
            load_config(bad)

    def test_defaults(self, sample_config_path):
        config = load_config(sample_config_path)
        assert config.defaults.cache_ttl_seconds == 3600
        assert config.defaults.output_format == "summary"
        assert config.defaults.max_response_size == 50000


class TestResolveServer:
    def test_stdio_server(self, monkeypatch):
        entry = ServerEntry(command="npx", args=["server"], env={})
        config = resolve_server("test", entry)
        assert config.name == "test"
        assert config.command == "npx"
        assert config.is_stdio is True

    def test_env_var_resolution(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        entry = ServerEntry(
            command="npx", args=["server"], env={"TOKEN": "${MY_TOKEN}"}
        )
        config = resolve_server("test", entry)
        assert config.env["TOKEN"] == "secret123"

    def test_missing_env_var_raises(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR_ABC", raising=False)
        entry = ServerEntry(
            command="npx", env={"KEY": "${NONEXISTENT_VAR_ABC}"}
        )
        with pytest.raises(ValueError, match="NONEXISTENT_VAR_ABC"):
            resolve_server("test", entry)

    def test_sse_server(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "key123")
        entry = ServerEntry(
            url="https://example.com/sse",
            headers={"Authorization": "Bearer ${API_KEY}"},
        )
        config = resolve_server("remote", entry)
        assert config.is_sse is True
        assert config.headers["Authorization"] == "Bearer key123"


class TestGetServerConfig:
    def test_found(self, sample_config, monkeypatch):
        # Need env vars for github server (but filesystem doesn't need them)
        config_server = get_server_config("filesystem", sample_config)
        assert config_server.name == "filesystem"

    def test_not_found(self, sample_config):
        with pytest.raises(ConfigError, match="not found"):
            get_server_config("nonexistent", sample_config)


class TestListServerNames:
    def test_returns_sorted(self, sample_config):
        names = list_server_names(sample_config)
        assert names == ["filesystem", "github", "remote"]


class TestCreateDefaultConfig:
    def test_creates_file(self, tmp_path):
        path = create_default_config(tmp_path / "config.json")
        assert path.is_file()
        data = json.loads(path.read_text())
        assert "mcpServers" in data
        assert "filesystem" in data["mcpServers"]

    def test_creates_parent_dirs(self, tmp_path):
        path = create_default_config(tmp_path / "deep" / "nested" / "config.json")
        assert path.is_file()
