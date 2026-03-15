"""Server configuration models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ServerConfig(BaseModel):
    """Immutable configuration for a single MCP server."""

    model_config = ConfigDict(frozen=True)

    name: str
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = {}
    url: str | None = None
    headers: dict[str, str] = {}
    cache_ttl: int = 3600

    @property
    def is_stdio(self) -> bool:
        return self.command is not None

    @property
    def is_sse(self) -> bool:
        return self.url is not None
