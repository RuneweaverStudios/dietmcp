"""Schema caching to avoid redundant introspection."""

from typing import Any
from datetime import datetime, timedelta


class SchemaCache:
    """Cache for GraphQL schemas to avoid double introspection."""

    def __init__(self):
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._ttl = timedelta(hours=1)  # Same as tool cache

    def get(self, key: str) -> Any | None:
        """Get cached schema if available and not expired."""
        if key not in self._cache:
            return None

        timestamp, schema = self._cache[key]
        if datetime.now() - timestamp > self._ttl:
            del self._cache[key]
            return None

        return schema

    def put(self, key: str, schema: Any) -> None:
        """Cache schema with current timestamp."""
        self._cache[key] = (datetime.now(), schema)

    def invalidate(self, key: str) -> None:
        """Remove schema from cache."""
        self._cache.pop(key, None)
