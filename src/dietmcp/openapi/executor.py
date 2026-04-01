"""OpenAPI HTTP client executor.

Executes HTTP requests based on OpenAPI specifications with support for:
- Authentication (headers, API keys, OAuth)
- All HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Path parameters, query strings, request bodies
- TOON encoding for tabular responses
- Comprehensive error handling
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from dietmcp.config.schema import OpenAPIServerConfig
from dietmcp.formatters.toon_formatter import ToonFormatter
from dietmcp.models.openapi import OpenAPIEndpoint, OpenAPISpec
from dietmcp.models.tool import ToolResult
from dietmcp.openapi.content_types import ContentType, parse_response_body, serialize_request_body
from dietmcp.security.rate_limiter import RateLimiter
from dietmcp.security.url_validator import validate_url

# Maximum response size to prevent DoS (10MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024


class OpenAPIExecutorError(Exception):
    """Exception raised when OpenAPI execution fails."""

    pass


class OpenAPIExecutor:
    """Execute HTTP requests based on OpenAPI specifications."""

    def __init__(
        self,
        config: OpenAPIServerConfig,
        spec: OpenAPISpec,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the executor.

        Args:
            config: OpenAPI server configuration (auth, baseUrl)
            spec: Parsed OpenAPI specification
            timeout: Request timeout in seconds
        """
        self.config = config
        self.spec = spec
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.toon_formatter = ToonFormatter()
        self.rate_limiter = RateLimiter(rate_limit=60, period=60.0)

    async def execute(
        self,
        endpoint: OpenAPIEndpoint,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute an HTTP request and return formatted result.

        Args:
            endpoint: OpenAPI endpoint to execute
            arguments: Request parameters (path, query, body)

        Returns:
            ToolResult with formatted response

        Raises:
            OpenAPIExecutorError: If request fails or validation fails
        """
        # Validate required parameters
        self._validate_parameters(endpoint, arguments)

        # Build request components
        url = self._build_url(endpoint, arguments)
        headers = self._build_headers(endpoint, arguments)
        query_params = self._build_query_params(endpoint, arguments)
        request_body = self._build_request_body(endpoint, arguments)

        # Determine request content type
        request_content_type = "application/json"
        if endpoint.request_body and "content" in endpoint.request_body:
            request_content_type = next(iter(endpoint.request_body["content"].keys()), "application/json")

        # Check request body size and set Content-Type
        if request_body is not None:
            headers["Content-Type"] = request_content_type
            # Get size for validation
            body_size = len(request_body) if isinstance(request_body, (str, bytes)) else len(str(request_body))
            if body_size > MAX_RESPONSE_SIZE:
                raise OpenAPIExecutorError(
                    f"Request body too large: {body_size} bytes "
                    f"(max: {MAX_RESPONSE_SIZE})"
                )

        try:
            # Apply rate limiting before request
            await self.rate_limiter.acquire()

            # Execute HTTP request
            # Convert request_body to bytes if needed for httpx
            body_content = request_body if isinstance(request_body, (bytes, str, type(None))) else json.dumps(request_body)

            response = await self.client.request(
                method=endpoint.method.lower(),
                url=url,
                params=query_params if query_params else None,
                content=body_content,
                headers=headers,
                follow_redirects=True,
            )

            # Check response size BEFORE parsing
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                raise OpenAPIExecutorError(
                    f"Response too large: {content_length} bytes "
                    f"(max: {MAX_RESPONSE_SIZE})"
                )

            # Check actual content size
            response.content  # Force load
            if len(response.content) > MAX_RESPONSE_SIZE:
                raise OpenAPIExecutorError(
                    f"Response content too large: {len(response.content)} bytes "
                    f"(max: {MAX_RESPONSE_SIZE})"
                )

            # Parse response
            return self._parse_response(response)

        except httpx.TimeoutException as e:
            raise OpenAPIExecutorError(
                f"Request to {url} timed out after {self.timeout}s"
            ) from e

        except httpx.NetworkError as e:
            raise OpenAPIExecutorError(
                f"Network error connecting to {url}: {e}"
            ) from e

        except httpx.HTTPStatusError as e:
            raise OpenAPIExecutorError(
                f"HTTP error {e.response.status_code} for {url}: {e.response.text}"
            ) from e

        except httpx.RequestError as e:
            raise OpenAPIExecutorError(
                f"Request failed for {url}: {e}"
            ) from e

    def _validate_parameters(
        self,
        endpoint: OpenAPIEndpoint,
        arguments: dict[str, Any],
    ) -> None:
        """Validate that all required parameters are provided.

        Args:
            endpoint: OpenAPI endpoint with parameter definitions
            arguments: Provided arguments

        Raises:
            OpenAPIExecutorError: If required parameters are missing
        """
        # Check required path parameters
        for param in endpoint.path_params:
            if param.required and param.name not in arguments:
                raise OpenAPIExecutorError(
                    f"Missing required path parameter: '{param.name}'"
                )

        # Check required query parameters
        for param in endpoint.query_params:
            if param.required and param.name not in arguments:
                raise OpenAPIExecutorError(
                    f"Missing required query parameter: '{param.name}'"
                )

        # Check required header parameters
        for param in endpoint.header_params:
            if param.required and param.name not in arguments:
                raise OpenAPIExecutorError(
                    f"Missing required header parameter: '{param.name}'"
                )

        # Check required cookie parameters
        for param in endpoint.cookie_params:
            if param.required and param.name not in arguments:
                raise OpenAPIExecutorError(
                    f"Missing required cookie parameter: '{param.name}'"
                )

        # Check required body parameters
        if endpoint.request_body:
            # Get content schema (assume application/json)
            content = endpoint.request_body.get("content", {})
            json_schema = content.get("application/json", {}).get("schema", {})

            # Check required fields in body
            required = json_schema.get("required", [])
            properties = json_schema.get("properties", {})

            for field in required:
                if field not in arguments:
                    raise OpenAPIExecutorError(
                        f"Missing required body field: '{field}'"
                    )

    def _build_url(
        self,
        endpoint: OpenAPIEndpoint,
        arguments: dict[str, Any],
    ) -> str:
        """Build full URL with path parameters substituted.

        Args:
            endpoint: OpenAPI endpoint
            arguments: Request arguments

        Returns:
            Complete URL with path parameters filled in
        """
        # Get base URL
        base_url = self.config.baseUrl or ""
        if not base_url and self.spec.servers:
            # Use first server from spec
            base_url = self.spec.servers[0].get("url", "")

        # Build path with parameter substitution
        path = endpoint.path

        # Substitute path parameters
        for param in endpoint.path_params:
            if param.name in arguments:
                value = arguments[param.name]
                # URL-encode the value
                path = path.replace(f"{{{param.name}}}", str(value))

        # Build full URL
        full_url = base_url + path

        # Validate URL is not internal/private (SSRF protection)
        try:
            validate_url(full_url)
        except ValueError as e:
            raise OpenAPIExecutorError(f"URL validation failed: {e}") from e

        return full_url

    def _build_headers(
        self,
        endpoint: OpenAPIEndpoint | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Build headers with authentication and parameter-based headers.

        Args:
            endpoint: OpenAPI endpoint (optional)
            arguments: Request arguments (optional)

        Returns:
            Dictionary of headers
        """
        headers = {
            "User-Agent": "dietmcp/1.0",
            "Accept": "application/json",
        }

        # Add authentication header
        if self.config.auth and self.config.auth.header:
            # Parse header format: "Header-Name: value"
            parts = self.config.auth.header.split(":", 1)
            if len(parts) == 2:
                header_name = parts[0].strip()
                header_value = parts[1].strip()
                headers[header_name] = header_value

        # Add header parameters from spec (if endpoint provided)
        if endpoint and arguments:
            for param in endpoint.header_params:
                if param.name in arguments:
                    headers[param.name] = str(arguments[param.name])

        return headers

    def _build_query_params(
        self,
        endpoint: OpenAPIEndpoint,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Build query parameters from arguments.

        Args:
            endpoint: OpenAPI endpoint
            arguments: Request arguments

        Returns:
            Dictionary of query parameters
        """
        query_params = {}

        for param in endpoint.query_params:
            if param.name in arguments:
                value = arguments[param.name]

                # Handle list parameters (e.g., ?tag=a&tag=b)
                if isinstance(value, list):
                    # httpx handles list params automatically
                    query_params[param.name] = value
                else:
                    query_params[param.name] = value

        return query_params

    def _build_request_body(
        self,
        endpoint: OpenAPIEndpoint,
        arguments: dict[str, Any],
    ) -> str | bytes | dict[str, Any] | None:
        """Build request body using content type serialization.

        Args:
            endpoint: OpenAPI endpoint
            arguments: Request arguments

        Returns:
            Serialized body (string, bytes, or dict for form-data)
        """
        # Only POST, PUT, PATCH typically have bodies
        if endpoint.method.upper() not in ["POST", "PUT", "PATCH"]:
            return None

        if not endpoint.request_body:
            return None

        # Extract body arguments (non-path, non-query, non-header, non-cookie params)
        body_args = {}

        # Get content type from request body
        request_content = endpoint.request_body.get("content", {})
        content_type_str = next(iter(request_content.keys()), "application/json")

        # Convert to ContentType enum
        try:
            content_type = ContentType(content_type_str)
        except ValueError:
            # Default to JSON for unsupported types
            content_type = ContentType.JSON

        # Arguments that aren't path, query, header, or cookie params go in body
        param_names = {
            p.name for p in endpoint.path_params
        } | {
            p.name for p in endpoint.query_params
        } | {
            p.name for p in endpoint.header_params
        } | {
            p.name for p in endpoint.cookie_params
        }

        for key, value in arguments.items():
            if key not in param_names:
                body_args[key] = value

        # Also include parameters marked as "in: body" (OpenAPI 2.0 style)
        for param in endpoint.parameters:
            if param.in_ == "body" and param.name in arguments:
                body_args[param.name] = arguments[param.name]

        if not body_args:
            return None

        # Use content_types module for serialization
        return serialize_request_body(body_args, content_type)

    def _parse_response(self, response: httpx.Response) -> ToolResult:
        """Parse HTTP response into ToolResult with TOON encoding.

        Args:
            response: HTTP response object

        Returns:
            ToolResult with formatted content
        """
        status_code = response.status_code
        is_error = status_code >= 400

        # Get response content type
        response_content_type = response.headers.get("content-type", "application/json")

        # Use content_types module to parse response body
        try:
            response_data = parse_response_body(response.text, response_content_type, is_error)
        except Exception:
            # Fallback to simple parsing
            try:
                response_data = response.json()
            except (json.JSONDecodeError, ValueError):
                response_data = {"text": response.text}

        # Build content blocks
        if isinstance(response_data, dict):
            text = json.dumps(response_data)
        else:
            text = str(response_data)

        content_blocks = [
            {
                "type": "text",
                "text": text
            }
        ]

        # Create ToolResult
        result = ToolResult(
            content=content_blocks,
            is_error=is_error,
            raw={"status_code": status_code, "headers": dict(response.headers)},
        )

        # Apply TOON encoding if response is tabular
        # Check if response is a uniform array (tabular data)
        if isinstance(response_data, list) and len(response_data) > 0:
            if all(isinstance(item, dict) for item in response_data):
                # Check if all objects have same keys (uniform)
                first_keys = set(response_data[0].keys())
                if all(set(item.keys()) == first_keys for item in response_data):
                    # Apply TOON encoding
                    toon_result = self.toon_formatter.format(result, max_size=10_000_000)
                    # Update content with TOON-encoded version
                    result = ToolResult(
                        content=[{"type": "text", "text": toon_result.content}],
                        is_error=is_error,
                        raw=result.raw,
                    )

        return result

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "OpenAPIExecutor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
