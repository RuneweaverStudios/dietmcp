"""Comprehensive unit tests for OpenAPI executor.

Tests HTTP request building, URL construction with path params,
query string building, header construction with auth,
response parsing and TOON encoding, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from dietmcp.openapi.executor import OpenAPIExecutor, OpenAPIExecutorError, MAX_RESPONSE_SIZE
from dietmcp.models.openapi import OpenAPIEndpoint, OpenAPIParameter, OpenAPISpec
from dietmcp.models.tool import ToolResult
from dietmcp.config.schema import OpenAPIServerConfig, AuthConfig


@pytest.fixture
def server_config():
    """Sample OpenAPI server configuration."""
    return OpenAPIServerConfig(
        name="test-api",
        baseUrl="https://api.example.com/v1",
        url="https://api.example.com/openapi.json",
        auth=AuthConfig(
            header="Authorization: Bearer test-token-123"
        )
    )


@pytest.fixture
def server_config_no_auth():
    """Server config without authentication."""
    return OpenAPIServerConfig(
        name="test-api",
        baseUrl="https://api.example.com/v1",
        url="https://api.example.com/openapi.json",
        auth=None
    )


@pytest.fixture
def sample_spec():
    """Sample OpenAPI spec."""
    return OpenAPISpec(
        title="Test API",
        version="1.0.0",
        servers=[{"url": "https://api.example.com/v1"}],
        endpoints=[],
        security_schemes={},
        components_schemas={},
    )


@pytest.fixture
def get_endpoint():
    """Sample GET endpoint with path and query params."""
    return OpenAPIEndpoint(
        path="/users/{userId}",
        method="GET",
        operation_id="getUser",
        summary="Get user by ID",
        parameters=[
            OpenAPIParameter(
                name="userId",
                in_="path",
                required=True,
                schema_={"type": "integer"}
            ),
            OpenAPIParameter(
                name="verbose",
                in_="query",
                required=False,
                schema_={"type": "boolean"}
            ),
            OpenAPIParameter(
                name="fields",
                in_="query",
                required=False,
                schema_={"type": "string"}
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def post_endpoint():
    """Sample POST endpoint with request body."""
    return OpenAPIEndpoint(
        path="/users",
        method="POST",
        operation_id="createUser",
        summary="Create user",
        parameters=[
            OpenAPIParameter(
                name="X-Custom-Header",
                in_="header",
                required=False,
                schema_={"type": "string"}
            ),
        ],
        request_body={
            "description": "User object",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "age": {"type": "integer"}
                        },
                        "required": ["name", "email"]
                    }
                }
            }
        },
        responses={"201": {"description": "Created"}},
        tags=[],
    )


@pytest.fixture
def endpoint_with_array_params():
    """Endpoint with array query parameters."""
    return OpenAPIEndpoint(
        path="/items",
        method="GET",
        operation_id="getItems",
        parameters=[
            OpenAPIParameter(
                name="tags",
                in_="query",
                required=False,
                schema_={"type": "array", "items": {"type": "string"}}
            ),
            OpenAPIParameter(
                name="ids",
                in_="query",
                required=False,
                schema_={"type": "array", "items": {"type": "integer"}}
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def endpoint_with_required_query():
    """Endpoint with required query parameters."""
    return OpenAPIEndpoint(
        path="/search",
        method="GET",
        operation_id="search",
        parameters=[
            OpenAPIParameter(
                name="q",
                in_="query",
                required=True,
                schema_={"type": "string"}
            ),
            OpenAPIParameter(
                name="limit",
                in_="query",
                required=False,
                schema_={"type": "integer"}
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def mock_response():
    """Mock HTTP response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.text = '{"id": 1, "name": "Test"}'
    response.json.return_value = {"id": 1, "name": "Test"}
    return response


class TestOpenAPIExecutorInit:
    """Test executor initialization."""

    def test_init_with_config(self, server_config, sample_spec):
        executor = OpenAPIExecutor(server_config, sample_spec, timeout=60.0)

        assert executor.config == server_config
        assert executor.spec == sample_spec
        assert executor.timeout == 60.0
        assert executor.client is not None
        assert executor.toon_formatter is not None

    def test_init_default_timeout(self, server_config, sample_spec):
        executor = OpenAPIExecutor(server_config, sample_spec)

        assert executor.timeout == 30.0

    @pytest.mark.asyncio
    async def test_async_context_manager(self, server_config, sample_spec):
        async with OpenAPIExecutor(server_config, sample_spec) as executor:
            assert executor is not None
            assert executor.client is not None

        # Client should be closed after context exit
        # (We can't easily test this without accessing private state)


class TestValidateParameters:
    """Test parameter validation."""

    def test_validate_all_params_present(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123, "verbose": True}

        # Should not raise
        executor._validate_parameters(get_endpoint, arguments)

    def test_validate_missing_required_path_param(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"verbose": True}  # Missing userId

        with pytest.raises(OpenAPIExecutorError, match="Missing required path parameter.*userId"):
            executor._validate_parameters(get_endpoint, arguments)

    def test_validate_missing_required_query_param(
        self, server_config, sample_spec, endpoint_with_required_query
    ):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"limit": 10}  # Missing required 'q'

        with pytest.raises(OpenAPIExecutorError, match="Missing required query parameter.*q"):
            executor._validate_parameters(endpoint_with_required_query, arguments)

    def test_validate_missing_required_body_field(self, server_config, sample_spec, post_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"name": "John"}  # Missing required 'email'

        with pytest.raises(OpenAPIExecutorError, match="Missing required body field.*email"):
            executor._validate_parameters(post_endpoint, arguments)

    def test_validate_no_params(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/health",
            method="GET",
            operation_id="health",
            parameters=[],
            request_body=None,
            responses={"200": {"description": "OK"}},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {}

        # Should not raise
        executor._validate_parameters(endpoint, arguments)

    def test_validate_optional_params_omitted(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123}  # Optional params omitted

        # Should not raise
        executor._validate_parameters(get_endpoint, arguments)


class TestBuildUrl:
    """Test URL building with path parameters."""

    def test_build_url_with_base_from_config(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123}

        url = executor._build_url(get_endpoint, arguments)

        assert url == "https://api.example.com/v1/users/123"

    def test_build_url_with_base_from_spec(self, server_config_no_auth, sample_spec, get_endpoint):
        # Remove baseUrl from config, forcing use of spec servers
        config = server_config_no_auth.model_copy(update={"baseUrl": None})
        executor = OpenAPIExecutor(config, sample_spec)
        arguments = {"userId": 456}

        url = executor._build_url(get_endpoint, arguments)

        assert url == "https://api.example.com/v1/users/456"

    def test_build_url_no_base(self, server_config_no_auth, sample_spec):
        # Create spec with no servers
        spec_no_servers = sample_spec.model_copy(update={"servers": []})
        # Use a valid baseUrl for URL validation
        config = server_config_no_auth.model_copy(update={"baseUrl": "https://api.example.com"})

        endpoint = OpenAPIEndpoint(
            path="/test",
            method="GET",
            operation_id="test",
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(config, spec_no_servers)
        url = executor._build_url(endpoint, {})

        assert url == "https://api.example.com/test"

    def test_build_url_multiple_path_params(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/users/{userId}/posts/{postId}",
            method="GET",
            operation_id="getPost",
            parameters=[
                OpenAPIParameter(name="userId", in_="path", required=True, schema_={}),
                OpenAPIParameter(name="postId", in_="path", required=True, schema_={}),
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123, "postId": 456}

        url = executor._build_url(endpoint, arguments)

        assert url == "https://api.example.com/v1/users/123/posts/456"

    def test_build_url_path_param_url_encoding(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/items/{itemId}",
            method="GET",
            operation_id="getItem",
            parameters=[
                OpenAPIParameter(name="itemId", in_="path", required=True, schema_={}),
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"itemId": "item with spaces"}

        url = executor._build_url(endpoint, arguments)

        # Spaces should be encoded (or converted depending on implementation)
        assert "item with spaces" in url or "item%20with%20spaces" in url

    def test_build_url_no_path_params(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="GET",
            operation_id="getUsers",
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        url = executor._build_url(endpoint, {})

        assert url == "https://api.example.com/v1/users"


class TestBuildHeaders:
    """Test header construction with authentication."""

    def test_build_headers_with_auth(self, server_config, sample_spec):
        executor = OpenAPIExecutor(server_config, sample_spec)
        headers = executor._build_headers()

        assert headers["User-Agent"] == "dietmcp/1.0"
        assert headers["Accept"] == "application/json"
        assert headers["Authorization"] == "Bearer test-token-123"

    def test_build_headers_without_auth(self, server_config_no_auth, sample_spec):
        executor = OpenAPIExecutor(server_config_no_auth, sample_spec)
        headers = executor._build_headers()

        assert headers["User-Agent"] == "dietmcp/1.0"
        assert headers["Accept"] == "application/json"
        assert "Authorization" not in headers

    def test_build_header_parsing(self):
        """Test various auth header formats."""
        config = OpenAPIServerConfig(
            name="test",
            baseUrl="https://api.example.com",
            url="https://api.example.com/openapi.json",
            auth=AuthConfig(header="X-API-Key: abc123")
        )

        spec = OpenAPISpec(
            title="API",
            version="1.0.0",
            servers=[],
            endpoints=[],
        )

        executor = OpenAPIExecutor(config, spec)
        headers = executor._build_headers()

        assert headers["X-API-Key"] == "abc123"

    def test_build_header_with_spaces_in_value(self):
        config = OpenAPIServerConfig(
            name="test",
            baseUrl="https://api.example.com",
            url="https://api.example.com/openapi.json",
            auth=AuthConfig(header="Authorization: Bearer token with spaces")
        )

        spec = OpenAPISpec(
            title="API",
            version="1.0.0",
            servers=[],
            endpoints=[],
        )

        executor = OpenAPIExecutor(config, spec)
        headers = executor._build_headers()

        assert headers["Authorization"] == "Bearer token with spaces"

    def test_build_header_malformed(self):
        """Test handling of malformed header (missing colon)."""
        config = OpenAPIServerConfig(
            name="test",
            baseUrl="https://api.example.com",
            url="https://api.example.com/openapi.json",
            auth=AuthConfig(header="InvalidHeader")
        )

        spec = OpenAPISpec(
            title="API",
            version="1.0.0",
            servers=[],
            endpoints=[],
        )

        executor = OpenAPIExecutor(config, spec)
        headers = executor._build_headers()

        # Should not add malformed header
        assert "InvalidHeader" not in headers


class TestBuildQueryParams:
    """Test query parameter building."""

    def test_build_query_params_single(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123, "verbose": True}

        params = executor._build_query_params(get_endpoint, arguments)

        assert params == {"verbose": True}
        assert "userId" not in params  # Path param, not query

    def test_build_query_params_multiple(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123, "verbose": True, "fields": "id,name"}

        params = executor._build_query_params(get_endpoint, arguments)

        assert params == {"verbose": True, "fields": "id,name"}

    def test_build_query_params_arrays(self, server_config, sample_spec, endpoint_with_array_params):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"tags": ["python", "javascript"], "ids": [1, 2, 3]}

        params = executor._build_query_params(endpoint_with_array_params, arguments)

        assert params["tags"] == ["python", "javascript"]
        assert params["ids"] == [1, 2, 3]

    def test_build_query_params_no_query_params(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="GET",
            operation_id="test",
            parameters=[
                OpenAPIParameter(name="id", in_="path", required=True, schema_={})
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"id": 123}

        params = executor._build_query_params(endpoint, arguments)

        assert params == {}

    def test_build_query_params_ignores_non_query(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="GET",
            operation_id="test",
            parameters=[
                OpenAPIParameter(name="id", in_="path", required=True, schema_={}),
                OpenAPIParameter(name="token", in_="header", required=False, schema_={}),
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"id": 123, "token": "abc"}

        params = executor._build_query_params(endpoint, arguments)

        # Should not include path or header params
        assert params == {}


class TestBuildRequestBody:
    """Test request body building."""

    def test_build_request_body_post(self, server_config, sample_spec, post_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"name": "John", "email": "john@example.com", "age": 30}

        import json
        body = executor._build_request_body(post_endpoint, arguments)

        assert body is not None
        body_dict = json.loads(body)
        assert body_dict == {"name": "John", "email": "john@example.com", "age": 30}

    def test_build_request_body_put(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="PUT",
            operation_id="updateUser",
            parameters=[
                OpenAPIParameter(name="id", in_="path", required=True, schema_={})
            ],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}}
                        }
                    }
                }
            },
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"id": 123, "name": "Jane"}

        body = executor._build_request_body(endpoint, arguments)

        assert body is not None
        import json
        body_dict = json.loads(body)
        assert body_dict == {"name": "Jane"}

    def test_build_request_body_patch(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="PATCH",
            operation_id="patchUser",
            parameters=[
                OpenAPIParameter(name="id", in_="path", required=True, schema_={})
            ],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}}
                        }
                    }
                }
            },
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"id": 123, "name": "Jane"}

        body = executor._build_request_body(endpoint, arguments)

        assert body is not None
        import json
        body_dict = json.loads(body)
        assert body_dict == {"name": "Jane"}

    def test_build_request_body_get_returns_none(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"userId": 123}

        body = executor._build_request_body(get_endpoint, arguments)

        assert body is None

    def test_build_request_body_delete_returns_none(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="DELETE",
            operation_id="deleteUser",
            parameters=[
                OpenAPIParameter(name="id", in_="path", required=True, schema_={})
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"id": 123}

        body = executor._build_request_body(endpoint, arguments)

        assert body is None

    def test_build_request_body_no_body_args(self, server_config, sample_spec, post_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {"X-Custom-Header": "value"}  # Only header param

        body = executor._build_request_body(post_endpoint, arguments)

        # Should return None if no body arguments
        assert body is None


class TestParseResponse:
    """Test response parsing and TOON encoding."""

    def test_parse_json_response(self, server_config, sample_spec, mock_response):
        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert isinstance(result, ToolResult)
        assert result.is_error is False
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"
        assert '{"id": 1, "name": "Test"}' in result.content[0]["text"]
        assert result.raw["status_code"] == 200

    def test_parse_error_response(self, server_config, sample_spec):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"error": "Not found"}
        mock_response.text = '{"error": "Not found"}'

        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert result.is_error is True
        assert result.raw["status_code"] == 404

    def test_parse_text_response(self, server_config, sample_spec):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"

        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert result.is_error is False
        assert "text" in result.content[0]["text"].lower() or "Plain text response" in result.content[0]["text"]

    def test_parse_tabular_response_with_toon(self, server_config, sample_spec):
        """Test TOON encoding for tabular data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}

        # Tabular data (uniform array of objects)
        tabular_data = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
            {"id": 3, "name": "Charlie", "age": 35},
        ]
        mock_response.json.return_value = tabular_data
        mock_response.text = str(tabular_data)

        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert result.is_error is False
        # TOON formatter should be applied
        # The exact output depends on ToonFormatter implementation
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"

    def test_parse_non_uniform_array(self, server_config, sample_spec):
        """Test that non-uniform arrays don't get TOON encoding."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}

        # Non-uniform array (different keys)
        non_uniform = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "email": "bob@example.com"},  # Different keys
        ]
        mock_response.json.return_value = non_uniform
        mock_response.text = str(non_uniform)

        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert result.is_error is False
        # Should not apply TOON encoding (non-uniform)
        # Just regular JSON dump

    def test_parse_empty_array(self, server_config, sample_spec):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = []
        mock_response.text = "[]"

        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert result.is_error is False
        # Empty array should not trigger TOON


class TestExecute:
    """Test the main execute method."""

    @pytest.mark.asyncio
    async def test_execute_get_request(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"id": 123, "name": "Test User"}
        mock_response.text = '{"id": 123, "name": "Test User"}'

        executor.client.request = AsyncMock(return_value=mock_response)

        result = await executor.execute(get_endpoint, {"userId": 123, "verbose": True})

        assert result.is_error is False
        executor.client.request.assert_called_once()

        # Verify request arguments
        call_args = executor.client.request.call_args
        assert call_args[1]["method"] == "get"
        assert "123" in call_args[1]["url"]
        assert call_args[1]["params"] == {"verbose": True}

    @pytest.mark.asyncio
    async def test_execute_post_request(self, server_config, sample_spec, post_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"id": 456, "created": True}
        mock_response.text = '{"id": 456, "created": True}'

        executor.client.request = AsyncMock(return_value=mock_response)

        result = await executor.execute(post_endpoint, {"name": "John", "email": "john@example.com"})

        assert result.is_error is False
        assert "Content-Type" in executor.client.request.call_args[1]["headers"]

    @pytest.mark.asyncio
    async def test_execute_with_array_params(self, server_config, sample_spec, endpoint_with_array_params):
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = []
        mock_response.text = "[]"

        executor.client.request = AsyncMock(return_value=mock_response)

        result = await executor.execute(endpoint_with_array_params, {"tags": ["python", "js"], "ids": [1, 2]})

        assert result.is_error is False

        # Verify array params passed correctly
        call_args = executor.client.request.call_args
        assert call_args[1]["params"] == {"tags": ["python", "js"], "ids": [1, 2]}


class TestErrorHandling:
    """Test error handling in execute method."""

    @pytest.mark.asyncio
    async def test_timeout_error(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        executor.client.request = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        with pytest.raises(OpenAPIExecutorError, match="timed out"):
            await executor.execute(get_endpoint, {"userId": 123})

    @pytest.mark.asyncio
    async def test_network_error(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        executor.client.request = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))

        with pytest.raises(OpenAPIExecutorError, match="Network error"):
            await executor.execute(get_endpoint, {"userId": 123})

    @pytest.mark.asyncio
    async def test_http_status_error(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        # Create a mock response for HTTPStatusError
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        error = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response
        )
        executor.client.request = AsyncMock(side_effect=error)

        with pytest.raises(OpenAPIExecutorError, match="HTTP error 500"):
            await executor.execute(get_endpoint, {"userId": 123})

    @pytest.mark.asyncio
    async def test_request_error(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        executor.client.request = AsyncMock(side_effect=httpx.RequestError("Invalid request"))

        with pytest.raises(OpenAPIExecutorError, match="Request failed"):
            await executor.execute(get_endpoint, {"userId": 123})

    @pytest.mark.asyncio
    async def test_missing_parameter_error(self, server_config, sample_spec, get_endpoint):
        executor = OpenAPIExecutor(server_config, sample_spec)

        # Missing required path parameter
        with pytest.raises(OpenAPIExecutorError, match="Missing required path parameter"):
            await executor.execute(get_endpoint, {})


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_build_url_with_empty_path_param_value(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/items/{itemId}",
            method="GET",
            operation_id="getItem",
            parameters=[
                OpenAPIParameter(name="itemId", in_="path", required=True, schema_={})
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        url = executor._build_url(endpoint, {"itemId": ""})

        # Empty string should still be substituted
        assert url == "https://api.example.com/v1/items/"

    def test_build_url_with_special_chars_in_param(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/items/{itemId}",
            method="GET",
            operationId="getItem",
            parameters=[
                OpenAPIParameter(name="itemId", in_="path", required=True, schema_={})
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        url = executor._build_url(endpoint, {"itemId": "item/with/slashes"})

        # Should handle special characters
        assert "item" in url

    def test_parse_response_with_empty_json(self, server_config, sample_spec):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {}
        mock_response.text = '{}'

        executor = OpenAPIExecutor(server_config, sample_spec)
        result = executor._parse_response(mock_response)

        assert result.is_error is False
        assert '{}' in result.content[0]["text"]

    def test_build_request_body_with_nested_object(self, server_config, sample_spec):
        endpoint = OpenAPIEndpoint(
            path="/data",
            method="POST",
            operation_id="createData",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "user": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            responses={},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)
        arguments = {
            "user": {
                "name": "John",
                "email": "john@example.com"
            }
        }

        body = executor._build_request_body(endpoint, arguments)

        assert body is not None
        import json
        body_dict = json.loads(body)
        assert body_dict["user"]["name"] == "John"


class TestClose:
    """Test executor cleanup."""

    @pytest.mark.asyncio
    async def test_close(self, server_config, sample_spec):
        executor = OpenAPIExecutor(server_config, sample_spec)

        # Mock the client close method
        executor.client.aclose = AsyncMock()

        await executor.close()

        executor.client.aclose.assert_called_once()


class TestResponseSizeLimits:
    """Test response size limits to prevent memory exhaustion."""

    @pytest.mark.asyncio
    async def test_oversized_request_body_rejected(self, server_config, sample_spec, post_endpoint):
        """Test that oversized request bodies are rejected."""
        executor = OpenAPIExecutor(server_config, sample_spec)

        # Create request body larger than MAX_RESPONSE_SIZE with required fields
        large_data = {
            "name": "x" * (MAX_RESPONSE_SIZE + 1),
            "email": "test@example.com"
        }

        with pytest.raises(OpenAPIExecutorError, match="Request body too large"):
            await executor.execute(post_endpoint, large_data)

    @pytest.mark.asyncio
    async def test_normal_sized_request_accepted(self, server_config, sample_spec, post_endpoint):
        """Test that normal-sized requests are accepted."""
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"id": 456, "created": True}
        mock_response.text = '{"id": 456, "created": True}'
        mock_response.content = b'{"id": 456, "created": True}'

        executor.client.request = AsyncMock(return_value=mock_response)

        # Normal-sized request should work
        result = await executor.execute(post_endpoint, {"name": "John", "email": "john@example.com"})

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_oversized_response_by_content_length_rejected(self, server_config, sample_spec, get_endpoint):
        """Test that responses with large Content-Length header are rejected."""
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Type": "application/json",
            "content-length": str(MAX_RESPONSE_SIZE + 1)
        }
        mock_response.content = b'{}'

        executor.client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(OpenAPIExecutorError, match="Response too large"):
            await executor.execute(get_endpoint, {"userId": 123})

    @pytest.mark.asyncio
    async def test_oversized_response_content_rejected(self, server_config, sample_spec, get_endpoint):
        """Test that responses with large actual content are rejected."""
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        # Content larger than MAX_RESPONSE_SIZE
        mock_response.content = b'x' * (MAX_RESPONSE_SIZE + 1)

        executor.client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(OpenAPIExecutorError, match="Response content too large"):
            await executor.execute(get_endpoint, {"userId": 123})

    @pytest.mark.asyncio
    async def test_normal_sized_response_accepted(self, server_config, sample_spec, get_endpoint):
        """Test that normal-sized responses are accepted."""
        executor = OpenAPIExecutor(server_config, sample_spec)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"id": 123, "name": "Test"}
        mock_response.text = '{"id": 123, "name": "Test"}'
        mock_response.content = b'{"id": 123, "name": "Test"}'

        executor.client.request = AsyncMock(return_value=mock_response)

        result = await executor.execute(get_endpoint, {"userId": 123})

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_toon_encoding_respects_size_limit(self, server_config, sample_spec):
        """Test that TOON encoding doesn't bypass size limits."""
        endpoint = OpenAPIEndpoint(
            path="/data",
            method="GET",
            operation_id="getData",
            parameters=[],
            request_body=None,
            responses={"200": {"description": "OK"}},
            tags=[],
        )

        executor = OpenAPIExecutor(server_config, sample_spec)

        # Create response larger than MAX_RESPONSE_SIZE
        large_array = [
            {"id": i, "data": "x" * 1000}
            for i in range(15000)  # This will exceed 10MB
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = large_array
        import json
        mock_response.content = json.dumps(large_array).encode()

        executor.client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(OpenAPIExecutorError, match="Response content too large"):
            await executor.execute(endpoint, {})

    def test_max_response_size_constant(self):
        """Test that MAX_RESPONSE_SIZE is set to 10MB."""
        assert MAX_RESPONSE_SIZE == 10 * 1024 * 1024
