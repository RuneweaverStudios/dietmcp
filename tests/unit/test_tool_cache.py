"""Tests for file-based tool cache."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dietmcp.cache.cache_key import make_cache_key
from dietmcp.cache.tool_cache import ToolCache
from dietmcp.models.server import ServerConfig
from dietmcp.models.tool import ToolDefinition


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def cache(cache_dir: Path) -> ToolCache:
    return ToolCache(cache_dir)


@pytest.fixture
def server_config() -> ServerConfig:
    return ServerConfig(
        name="test-server",
        command="echo",
        args=("hello",),
        cache_ttl=3600,
    )


@pytest.fixture
def tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="tool_a",
            description="First tool",
            input_schema={"properties": {"x": {"type": "string"}}},
            server_name="test-server",
        ),
        ToolDefinition(
            name="tool_b",
            description="Second tool",
            input_schema={},
            server_name="test-server",
        ),
    ]


class TestCacheKey:
    def test_deterministic(self):
        cfg = ServerConfig(name="s", command="cmd", args=("a",))
        assert make_cache_key(cfg) == make_cache_key(cfg)

    def test_different_for_different_servers(self):
        cfg1 = ServerConfig(name="s1", command="cmd")
        cfg2 = ServerConfig(name="s2", command="cmd")
        assert make_cache_key(cfg1) != make_cache_key(cfg2)

    def test_sse_key(self):
        cfg = ServerConfig(name="remote", url="https://example.com")
        key = make_cache_key(cfg)
        assert len(key) == 16


class TestToolCache:
    def test_cache_miss(self, cache, server_config):
        result = cache.get("test-server", server_config)
        assert result is None

    def test_put_and_get(self, cache, server_config, tools):
        cache.put("test-server", server_config, tools)
        result = cache.get("test-server", server_config)

        assert result is not None
        assert len(result) == 2
        assert result[0].name == "tool_a"
        assert result[1].name == "tool_b"

    def test_cache_creates_directory(self, cache_dir, server_config, tools):
        assert not cache_dir.exists()
        cache = ToolCache(cache_dir)
        cache.put("test-server", server_config, tools)
        assert cache_dir.exists()

    def test_ttl_expiration(self, cache, cache_dir, server_config, tools):
        cache.put("test-server", server_config, tools)

        # Manually set cached_at to 2 hours ago
        key = make_cache_key(server_config)
        path = cache_dir / f"{key}.json"
        data = json.loads(path.read_text())
        data["cached_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat()
        path.write_text(json.dumps(data))

        result = cache.get("test-server", server_config)
        assert result is None  # Expired

    def test_invalidate(self, cache, server_config, tools):
        cache.put("test-server", server_config, tools)
        assert cache.get("test-server", server_config) is not None

        cache.invalidate(server_config)
        assert cache.get("test-server", server_config) is None

    def test_invalidate_all(self, cache, server_config, tools):
        cache.put("test-server", server_config, tools)

        cfg2 = ServerConfig(name="other", command="echo", args=("world",))
        cache.put("other", cfg2, tools)

        cache.invalidate_all()
        assert cache.get("test-server", server_config) is None
        assert cache.get("other", cfg2) is None

    def test_corrupted_cache_returns_none(self, cache, cache_dir, server_config):
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = make_cache_key(server_config)
        path = cache_dir / f"{key}.json"
        path.write_text("not valid json{{{")

        result = cache.get("test-server", server_config)
        assert result is None

    def test_preserves_tool_schema(self, cache, server_config):
        tools = [
            ToolDefinition(
                name="complex",
                description="A complex tool",
                input_schema={
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}},
                        "mode": {"type": "string", "enum": ["fast", "slow"]},
                    },
                    "required": ["items"],
                },
                server_name="test-server",
            )
        ]
        cache.put("test-server", server_config, tools)
        result = cache.get("test-server", server_config)

        assert result is not None
        assert result[0].input_schema["properties"]["items"]["type"] == "array"
        assert result[0].input_schema["properties"]["mode"]["enum"] == ["fast", "slow"]
