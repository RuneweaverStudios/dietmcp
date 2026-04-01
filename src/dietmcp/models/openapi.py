"""OpenAPI specification models."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dietmcp.config.schema import AuthConfig


class SecurityScheme(BaseModel):
    """Immutable representation of an OpenAPI security scheme."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    name: str
    type: str  # apiKey, http, oauth2, openIdConnect, mutualTLS
    description: str | None = None
    in_: str | None = Field(default=None, alias="in")  # For apiKey: header, query, cookie
    scheme: str | None = None  # For http: bearer, basic, digest, etc.
    bearer_format: str | None = None  # For http bearer: JWT format
    flows: dict[str, Any] | None = None  # For oauth2: authorizationCode, implicit, etc.
    scopes: list[str] | None = None  # Available scopes
    open_id_connect_url: str | None = None  # For openIdConnect


class OpenAPIParameter(BaseModel):
    """Immutable representation of an OpenAPI parameter."""

    model_config = ConfigDict(frozen=True)

    name: str
    in_: str  # query, header, path, cookie
    description: str | None = None
    required: bool = False
    schema_: dict[str, Any] | None = None  # JSON Schema for the parameter
    example: Any = None
    style: str | None = None  # For path/query: matrix, label, form, simple
    explode: bool | None = None  # For path/query/header/cookie
    deprecated: bool = False
    allow_empty_value: bool = False  # For query params only


class OpenAPIEndpoint(BaseModel):
    """Immutable representation of an OpenAPI endpoint operation."""

    model_config = ConfigDict(frozen=True)

    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH, etc.
    operation_id: str | None = None
    summary: str | None = None
    description: str | None = None
    parameters: list[OpenAPIParameter] = []
    request_body: dict[str, Any] | None = None  # Request body schema
    responses: dict[str, dict[str, Any]] = {}  # Response codes and schemas
    success_schema: dict[str, Any] | None = None  # 2xx response schema
    error_schema: dict[str, Any] | None = None  # 4xx/5xx response schema
    tags: list[str] = []
    security: list[dict[str, list[str]]] = []  # Auth requirements
    # Grouped parameters by location (auto-computed from parameters)
    path_params: list[OpenAPIParameter] = []
    query_params: list[OpenAPIParameter] = []
    header_params: list[OpenAPIParameter] = []
    cookie_params: list[OpenAPIParameter] = []

    @model_validator(mode='after')
    def compute_grouped_parameters(self):
        """Auto-compute grouped parameters from parameters list if not explicitly set."""
        # Only compute if grouped params are empty and parameters is not
        if not self.path_params and not self.query_params and not self.header_params and not self.cookie_params:
            if self.parameters:
                # Compute grouped params from parameters list
                object.__setattr__(self, 'path_params', [p for p in self.parameters if p.in_ == "path"])
                object.__setattr__(self, 'query_params', [p for p in self.parameters if p.in_ == "query"])
                object.__setattr__(self, 'header_params', [p for p in self.parameters if p.in_ == "header"])
                object.__setattr__(self, 'cookie_params', [p for p in self.parameters if p.in_ == "cookie"])
        return self


class OpenAPISpec(BaseModel):
    """Immutable representation of a parsed OpenAPI specification."""

    model_config = ConfigDict(frozen=True)

    title: str
    version: str
    description: str | None = None
    servers: list[dict[str, str]] = []  # Server URLs
    endpoints: list[OpenAPIEndpoint] = []
    security_schemes: dict[str, dict[str, Any]] = {}  # Global auth schemes (raw)
    security_schemes_list: list[SecurityScheme] = []  # Structured security schemes
    components_schemas: dict[str, dict[str, Any]] = {}  # Reusable schemas
    raw_spec: dict[str, Any] = {}  # Original spec for reference

    def get_endpoints_by_tag(self, tag: str) -> list[OpenAPIEndpoint]:
        """Filter endpoints by tag."""
        return [ep for ep in self.endpoints if tag in ep.tags]

    def get_endpoint_by_id(self, operation_id: str) -> OpenAPIEndpoint | None:
        """Find endpoint by operation_id."""
        for ep in self.endpoints:
            if ep.operation_id == operation_id:
                return ep
        return None

    def get_security_scheme(self, scheme_name: str) -> dict[str, Any] | None:
        """Get security scheme details by name."""
        return self.security_schemes.get(scheme_name)

    def get_security_scheme_model(self, scheme_name: str) -> SecurityScheme | None:
        """Get structured security scheme by name."""
        for scheme in self.security_schemes_list:
            if scheme.name == scheme_name:
                return scheme
        return None

    def get_auth_headers(self, config: AuthConfig) -> dict[str, str]:
        """Convert security scheme to HTTP headers.

        Args:
            config: Authentication configuration with header string

        Returns:
            Dictionary of HTTP headers for authentication

        Examples:
            >>> config = AuthConfig(header="Authorization: Bearer ${TOKEN}")
            >>> spec.get_auth_headers(config)
            {"Authorization": "Bearer <token_value>"}

            >>> config = AuthConfig(header="X-API-Key: ${API_KEY}")
            >>> spec.get_auth_headers(config)
            {"X-API-Key": "<key_value>"}
        """
        headers = {}

        if config.header:
            # Parse "Authorization: Bearer ${TOKEN}" or "X-API-Key: ${KEY}"
            if ":" in config.header:
                key, value = config.header.split(":", 1)
                value = value.strip()
                # Resolve ${VAR} from environment (handles embedded vars like "Bearer ${TOKEN}")
                import re
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)
                for var_name in matches:
                    env_value = os.getenv(var_name, "")
                    value = value.replace(f"${{{var_name}}}", env_value)
                headers[key.strip()] = value

        return headers
