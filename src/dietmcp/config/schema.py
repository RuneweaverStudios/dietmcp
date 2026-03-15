"""Configuration file Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ServerEntry(BaseModel):
    """Raw server entry as it appears in the config file."""

    model_config = ConfigDict(frozen=True)

    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None
    headers: dict[str, str] = {}
    cache_ttl: int | None = None


class ConfigDefaults(BaseModel):
    """Global default settings."""

    model_config = ConfigDict(frozen=True)

    cache_ttl_seconds: int = 3600
    output_format: str = "summary"
    max_response_size: int = 50_000
    env_file: str | None = None


class DietMcpConfig(BaseModel):
    """Top-level configuration file model."""

    model_config = ConfigDict(frozen=True)

    mcpServers: dict[str, ServerEntry] = {}
    defaults: ConfigDefaults = ConfigDefaults()
