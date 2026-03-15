"""Cache key generation for tool schema caching."""

from __future__ import annotations

import hashlib

from dietmcp.models.server import ServerConfig


def make_cache_key(config: ServerConfig) -> str:
    """Generate a deterministic cache key from server configuration.

    The key is a SHA256 hash of the server's identity (command + args or url).
    Config changes automatically invalidate the cache.
    """
    identity_parts = [config.name]

    if config.is_stdio:
        identity_parts.append(config.command or "")
        identity_parts.extend(config.args)
    elif config.is_sse:
        identity_parts.append(config.url or "")

    identity = "|".join(identity_parts)
    return hashlib.sha256(identity.encode()).hexdigest()[:16]
