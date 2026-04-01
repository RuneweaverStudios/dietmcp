"""GraphQL executor for running queries and mutations.

This module provides execution capabilities for GraphQL operations, handling
authentication, error processing, and response formatting. Integrates with
the existing tool execution framework in core/executor.py.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from dietmcp.config.schema import GraphQLServerConfig
from dietmcp.formatters.toon_formatter import ToonFormatter
from dietmcp.graphql.generator import GraphQLQueryGenerator
from dietmcp.models.graphql import GraphQLSchema, GraphQLOperation
from dietmcp.models.tool import ToolResult
from dietmcp.security.rate_limiter import RateLimiter
from dietmcp.security.url_validator import validate_url

# Maximum response size to prevent DoS (10MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024


class GraphQLError(Exception):
    """Raised when GraphQL operation returns errors."""

    def __init__(self, errors: list[dict[str, Any]]):
        """Initialize with GraphQL errors array.

        Args:
            errors: GraphQL errors array from response
        """
        self.errors = errors
        messages = [err.get("message", "Unknown error") for err in errors]
        super().__init__("; ".join(messages))


class GraphQLExecutor:
    """Execute GraphQL queries and mutations with proper error handling.

    This executor:
    - Builds GraphQL queries from operation definitions
    - Handles authentication from server config
    - Executes HTTP requests with proper headers
    - Processes GraphQL errors and responses
    - Applies TOON encoding for tabular data
    - Returns consistent ToolResult format
    """

    def __init__(self, config: GraphQLServerConfig, timeout: float = 30.0) -> None:
        """Initialize executor with server configuration.

        Args:
            config: GraphQL server configuration with URL and auth
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.config = config
        self.timeout = timeout
        self.toon_formatter = ToonFormatter()
        self.rate_limiter = RateLimiter(rate_limit=60, period=60.0)

    async def execute(
        self,
        operation: GraphQLOperation,
        variables: dict[str, Any],
        schema: GraphQLSchema | None = None,
    ) -> ToolResult:
        """Execute GraphQL query/mutation and return result.

        Args:
            operation: GraphQL operation (query or mutation)
            variables: Variable values for the operation
            schema: GraphQL schema for field selection (required)

        Returns:
            ToolResult with formatted response

        Raises:
            GraphQLError: When GraphQL operation returns errors
            httpx.HTTPError: On network or HTTP errors
        """
        # Validate schema is provided
        if not schema:
            raise ValueError(f"Schema is required for GraphQL execution of operation {operation.name}")

        # Validate URL is not internal/private (SSRF protection)
        try:
            validate_url(self.config.url)
        except ValueError as e:
            raise ValueError(f"URL validation failed: {e}") from e

        # Build query using generator for proper field selection
        generator = GraphQLQueryGenerator(schema)
        query = generator.generate_query(operation, variables)

        # Prepare request
        headers = self._build_headers()
        payload = {
            "query": query,
            "variables": variables,
        }

        # Check request size
        import json
        payload_json = json.dumps(payload)
        if len(payload_json.encode('utf-8')) > MAX_RESPONSE_SIZE:
            raise ValueError(
                f"Request payload too large: {len(payload_json.encode('utf-8'))} bytes "
                f"(max: {MAX_RESPONSE_SIZE})"
            )

        # Execute request
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Apply rate limiting before request
            await self.rate_limiter.acquire()

            response = await client.post(
                self.config.url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            # Check response size BEFORE parsing
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                raise ValueError(
                    f"Response too large: {content_length} bytes "
                    f"(max: {MAX_RESPONSE_SIZE})"
                )

            # Check actual content size
            if len(response.content) > MAX_RESPONSE_SIZE:
                raise ValueError(
                    f"Response content too large: {len(response.content)} bytes "
                    f"(max: {MAX_RESPONSE_SIZE})"
                )

            data = await response.json()

        # Process response
        return self._process_response(data, operation.name)

    def _build_headers(self) -> dict[str, str]:
        """Build headers with auth from config.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
        }

        if self.config.auth and self.config.auth.header:
            # Parse header string (format: "Header-Name: value")
            parts = self.config.auth.header.split(":", 1)
            if len(parts) == 2:
                header_name = parts[0].strip()
                header_value = parts[1].strip()
                headers[header_name] = header_value

        return headers

    def _process_response(self, data: dict[str, Any], operation_name: str) -> ToolResult:
        """Process GraphQL response and convert to ToolResult.

        Args:
            data: Raw GraphQL response JSON
            operation_name: Name of the executed operation

        Returns:
            ToolResult with formatted content

        Raises:
            GraphQLError: When response contains errors
        """
        # Check for errors
        if "errors" in data and data["errors"]:
            errors = data["errors"]
            error_text = json.dumps(errors, indent=2)
            content_blocks = [{"type": "text", "text": error_text}]
            return ToolResult(
                content=content_blocks,
                is_error=True,
                raw=data,
            )

        # Extract data
        if "data" not in data:
            # No data and no errors - unusual but handle gracefully
            content_blocks = [
                {"type": "text", "text": json.dumps(data, indent=2)}
            ]
            return ToolResult(
                content=content_blocks,
                is_error=False,
                raw=data,
            )

        # Extract operation result
        response_data = data["data"]

        # Try to get the specific operation result
        if operation_name in response_data:
            result_data = response_data[operation_name]
        else:
            # Fallback to entire data field
            result_data = response_data

        # Format result
        content_blocks = [
            {"type": "text", "text": json.dumps(result_data, indent=2)}
        ]

        return ToolResult(
            content=content_blocks,
            is_error=False,
            raw=data,
        )

    def _extract_data(self, response: dict[str, Any]) -> Any:
        """Extract data field from GraphQL response.

        Args:
            response: GraphQL response JSON

        Returns:
            Data field content or None if missing
        """
        return response.get("data")
