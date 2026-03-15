"""Tests for credential loading and resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dietmcp.security.credentials import (
    collect_env,
    load_env_files,
    resolve_env_dict,
    resolve_template,
)


class TestResolveTemplate:
    def test_simple_var(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "abc123")
        result = resolve_template("Bearer ${MY_TOKEN}")
        assert result == "Bearer abc123"

    def test_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")
        result = resolve_template("${HOST}:${PORT}")
        assert result == "localhost:8080"

    def test_no_vars(self):
        result = resolve_template("plain string")
        assert result == "plain string"

    def test_missing_var_raises(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR_XYZ", raising=False)
        with pytest.raises(ValueError, match="NONEXISTENT_VAR_XYZ"):
            resolve_template("${NONEXISTENT_VAR_XYZ}")

    def test_env_dict_override(self):
        result = resolve_template("${MY_VAR}", env={"MY_VAR": "from_dict"})
        assert result == "from_dict"

    def test_env_dict_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "from_os")
        result = resolve_template("${MY_VAR}", env={"MY_VAR": "from_dict"})
        assert result == "from_dict"


class TestResolveEnvDict:
    def test_resolve_all(self):
        env = {"TOKEN": "secret123"}
        result = resolve_env_dict(
            {"GITHUB_TOKEN": "${TOKEN}", "PLAIN": "hello"}, extra_env=env
        )
        assert result == {"GITHUB_TOKEN": "secret123", "PLAIN": "hello"}


class TestLoadEnvFiles:
    def test_load_single_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        result = load_env_files(env_file)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_load_nonexistent(self, tmp_path):
        result = load_env_files(tmp_path / "nonexistent")
        assert result == {}

    def test_later_files_override(self, tmp_path):
        f1 = tmp_path / ".env1"
        f2 = tmp_path / ".env2"
        f1.write_text("KEY=value1\n")
        f2.write_text("KEY=value2\n")
        result = load_env_files(f1, f2)
        assert result["KEY"] == "value2"


class TestCollectEnv:
    def test_combines_dotenv_and_os(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("DOTENV_VAR=from_file\n")
        monkeypatch.setenv("OS_VAR", "from_os")

        result = collect_env([env_file])
        assert result["DOTENV_VAR"] == "from_file"
        assert result["OS_VAR"] == "from_os"

    def test_dotenv_overrides_os(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SHARED", "from_os")
        env_file = tmp_path / ".env"
        env_file.write_text("SHARED=from_file\n")

        result = collect_env([env_file])
        assert result["SHARED"] == "from_file"
