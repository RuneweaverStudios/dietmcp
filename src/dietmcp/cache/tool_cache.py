"""File-based tool schema cache with TTL expiration.

DEV NOTES:
- Cache uses atomic writes (write to temp file, then os.replace) to prevent
  corruption from concurrent dietmcp invocations. os.replace is atomic on POSIX.
- Cache keys are a 16-char SHA256 prefix of (server_name + command + args).
  This means config changes (e.g., different args) automatically invalidate
  the cache without explicit cleanup.
- The 1-hour default TTL balances freshness with performance. For servers that
  change frequently, users can set a per-server cache_ttl in config.
- We chose file-based caching over in-memory because dietmcp is invoked as
  a subprocess per call. There's no long-running process to hold memory state.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dietmcp.cache.cache_key import make_cache_key
from dietmcp.config.defaults import CACHE_DIR
from dietmcp.models.server import ServerConfig
from dietmcp.models.tool import ToolDefinition


class ToolCache:
    """File-based cache for MCP tool schemas.

    Each server's tools are stored in a separate JSON file under the cache
    directory. Files are invalidated based on the server's configured TTL.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or CACHE_DIR

    def get(
        self, server_name: str, config: ServerConfig
    ) -> list[ToolDefinition] | None:
        """Retrieve cached tools if they exist and haven't expired."""
        path = self._cache_path(config)
        if not path.is_file():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        cached_at = datetime.fromisoformat(data.get("cached_at", ""))
        ttl = data.get("ttl_seconds", config.cache_ttl)
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()

        if age > ttl:
            return None

        tools = []
        for raw_tool in data.get("tools", []):
            tools.append(
                ToolDefinition(
                    name=raw_tool["name"],
                    description=raw_tool["description"],
                    input_schema=raw_tool["input_schema"],
                    server_name=server_name,
                )
            )
        return tools

    def put(
        self,
        server_name: str,
        config: ServerConfig,
        tools: list[ToolDefinition],
    ) -> None:
        """Store tools in the cache with current timestamp."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "server_name": server_name,
            "config_key": make_cache_key(config),
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": config.cache_ttl,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ],
        }

        path = self._cache_path(config)
        # Atomic write: write to temp file then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self._cache_dir, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def invalidate(self, config: ServerConfig) -> None:
        """Remove the cache file for a specific server."""
        path = self._cache_path(config)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def invalidate_all(self) -> None:
        """Remove all cache files."""
        if not self._cache_dir.is_dir():
            return
        for file in self._cache_dir.glob("*.json"):
            try:
                file.unlink()
            except OSError:
                pass

    def _cache_path(self, config: ServerConfig) -> Path:
        key = make_cache_key(config)
        return self._cache_dir / f"{key}.json"
