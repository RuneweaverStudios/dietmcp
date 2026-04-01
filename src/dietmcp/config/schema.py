"""Configuration file Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthConfig(BaseModel):
    """Authentication configuration for API servers."""

    model_config = ConfigDict(frozen=True)

    header: str | None = Field(
        default=None,
        description="Header string with auth token, e.g., 'Authorization: Bearer ${TOKEN}' or 'X-API-Key: ${API_KEY}'",
    )
    oauth: dict | None = Field(
        default=None,
        description="OAuth configuration (future support)",
    )


class ServerEntry(BaseModel):
    """Raw MCP server entry as it appears in the config file."""

    model_config = ConfigDict(frozen=True)

    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None
    headers: dict[str, str] = {}
    cache_ttl: int | None = None


class OpenAPIServerConfig(BaseModel):
    """Configuration for an OpenAPI/REST API server."""

    model_config = ConfigDict(frozen=True)

    url: str = Field(
        ...,
        description="URL or file path to OpenAPI specification (JSON or YAML)",
    )
    auth: AuthConfig | None = Field(
        default=None,
        description="Authentication configuration",
    )
    baseUrl: str | None = Field(
        default=None,
        description="Override base URL from OpenAPI spec",
    )
    cacheTtl: int | None = Field(
        default=None,
        description="Cache TTL in seconds, overrides global default",
    )


class GraphQLServerConfig(BaseModel):
    """Configuration for a GraphQL API server."""

    model_config = ConfigDict(frozen=True)

    url: str = Field(
        ...,
        description="GraphQL endpoint URL",
    )
    auth: AuthConfig | None = Field(
        default=None,
        description="Authentication configuration",
    )
    cacheTtl: int | None = Field(
        default=None,
        description="Cache TTL in seconds, overrides global default",
    )


class ConfigDefaults(BaseModel):
    """Global default settings."""

    model_config = ConfigDict(frozen=True)

    cache_ttl_seconds: int = 3600
    output_format: str = "summary"
    max_response_size: int = 50_000
    env_file: str | None = None


class DietMcpConfig(BaseModel):
    """Top-level configuration file model.

    Supports three types of servers:
    - mcpServers: Model Context Protocol servers via stdio/SSE
    - openapiServers: REST APIs described by OpenAPI specs
    - graphqlServers: GraphQL endpoints
    """

    model_config = ConfigDict(frozen=True)

    mcpServers: dict[str, ServerEntry] = Field(default_factory=dict)
    openapiServers: dict[str, OpenAPIServerConfig] = Field(default_factory=dict)
    graphqlServers: dict[str, GraphQLServerConfig] = Field(default_factory=dict)
    defaults: ConfigDefaults = Field(default_factory=ConfigDefaults)
