"""Tests for GraphQL executor functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from dietmcp.config.schema import GraphQLServerConfig, AuthConfig
from dietmcp.graphql.executor import GraphQLExecutor, GraphQLError, MAX_RESPONSE_SIZE
from dietmcp.models.graphql import (
    GraphQLSchema,
    GraphQLOperation,
    GraphQLField,
    GraphQLArgument,
    GraphQLType,
)
from dietmcp.models.tool import ToolResult


@pytest.fixture
def graphql_config():
    """Create GraphQL server configuration."""
    return GraphQLServerConfig(
        url="https://api.example.com/graphql",
        auth=AuthConfig(
            header="Authorization: Bearer ghp_test_token"
        ),
    )


@pytest.fixture
def graphql_config_no_auth():
    """Create GraphQL server configuration without auth."""
    return GraphQLServerConfig(
        url="https://api.example.com/graphql",
    )


@pytest.fixture
def sample_schema():
    """Create sample GraphQL schema with User type."""
    return GraphQLSchema(
        query_type_name="Query",
        mutation_type_name=None,
        types={
            "User": GraphQLType(
                name="User",
                kind="OBJECT",
                description="A user",
                fields={
                    "login": GraphQLField(
                        name="login",
                        description="User login",
                        type_name="String",
                        type_kind="SCALAR",
                        args=[],
                    ),
                    "name": GraphQLField(
                        name="name",
                        description="User name",
                        type_name="String",
                        type_kind="SCALAR",
                        args=[],
                    ),
                    "email": GraphQLField(
                        name="email",
                        description="User email",
                        type_name="String",
                        type_kind="SCALAR",
                        args=[],
                    ),
                    "bio": GraphQLField(
                        name="bio",
                        description="User bio",
                        type_name="String",
                        type_kind="SCALAR",
                        args=[],
                    ),
                },
            ),
            "String": GraphQLType(
                name="String",
                kind="SCALAR",
                description="Scalar string",
                fields=None,
            ),
        },
        queries=[],
        mutations=[],
    )


@pytest.fixture
def sample_operation():
    """Create sample GraphQL operation."""
    return GraphQLOperation(
        name="user",
        description="Get a user",
        field=GraphQLField(
            name="user",
            description="Get a user",
            type_name="User",
            type_kind="OBJECT",
            args=[
                GraphQLArgument(
                    name="login",
                    type_name="String",
                    type_kind="SCALAR",
                    default_value=None,
                    description="User login",
                )
            ],
        ),
    )


@pytest.fixture
def sample_mutation():
    """Create sample GraphQL mutation."""
    return GraphQLOperation(
        name="addComment",
        description="Add a comment",
        field=GraphQLField(
            name="addComment",
            description="Add a comment",
            type_name="Comment",
            type_kind="OBJECT",
            args=[
                GraphQLArgument(
                    name="subjectId",
                    type_name="ID",
                    type_kind="SCALAR",
                    default_value=None,
                    description="Subject ID",
                ),
                GraphQLArgument(
                    name="body",
                    type_name="String",
                    type_kind="SCALAR",
                    default_value=None,
                    description="Comment body",
                ),
            ],
        ),
    )


@pytest.fixture
def executor(graphql_config):
    """Create GraphQLExecutor instance."""
    return GraphQLExecutor(graphql_config)


@pytest.fixture
def executor_no_auth(graphql_config_no_auth):
    """Create GraphQLExecutor instance without auth."""
    return GraphQLExecutor(graphql_config_no_auth)


class TestGraphQLExecutor:
    """Test suite for GraphQLExecutor."""

    def test_init(self, graphql_config):
        """Test executor initialization."""
        executor = GraphQLExecutor(graphql_config, timeout=60.0)
        assert executor.config == graphql_config
        assert executor.timeout == 60.0

    def test_init_default_timeout(self, graphql_config):
        """Test executor initialization with default timeout."""
        executor = GraphQLExecutor(graphql_config)
        assert executor.timeout == 30.0

    @pytest.mark.asyncio
    async def test_execute_query_success(self, executor, sample_operation, sample_schema):
        """Test successful query execution."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": {
                        "login": "octocat",
                        "name": "The Octocat",
                    }
                }
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)

        assert result.is_error is False
        assert len(result.content) > 0
        assert result.content[0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_execute_uses_field_selection(self, executor, sample_operation, sample_schema):
        """Test that executor uses GraphQLQueryGenerator for proper field selection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": {
                        "login": "octocat",
                        "name": "The Octocat",
                        "email": "octocat@example.com",
                        "bio": "GitHub mascot",
                    }
                }
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)

        # Verify the query was sent
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        query = call_kwargs["json"]["query"]

        # Query should include multiple fields, not just __typename
        assert "login" in query
        assert "name" in query

        # Should NOT be the old hardcoded __typename-only query
        assert "__typename" not in query or ("login" in query and "name" in query)

    @pytest.mark.asyncio
    async def test_execute_with_auth_headers(self, executor, sample_operation, sample_schema):
        """Test that auth headers are included in request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": {
                        "login": "octocat",
                    }
                }
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)

        # Verify auth header was included
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        headers = call_kwargs["headers"]
        assert "Authorization" in headers
        assert "Bearer ghp_test_token" in headers["Authorization"]

    @pytest.mark.asyncio
    async def test_execute_without_auth(self, executor_no_auth, sample_operation, sample_schema):
        """Test execution without authentication."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": {
                        "login": "octocat",
                    }
                }
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            await executor_no_auth.execute(sample_operation, {"login": "octocat"}, sample_schema)

        # Verify no Authorization header
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        headers = call_kwargs["headers"]
        assert "Authorization" not in headers
        assert "Content-Type" in headers

    @pytest.mark.asyncio
    async def test_execute_with_graphql_errors(self, executor, sample_operation, sample_schema):
        """Test handling of GraphQL errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": None
                },
                "errors": [
                    {
                        "message": "Could not resolve to a User",
                        "path": ["user"],
                    }
                ]
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await executor.execute(sample_operation, {"login": "nonexistent"}, sample_schema)

        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_execute_http_error(self, executor, sample_operation, sample_schema):
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}
        mock_response.content = b'{"error": "Unauthorized"}'
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_response.json = AsyncMock(return_value={"error": "Unauthorized"})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        # Make __aexit__ propagate exceptions
        async def mock_aexit(exc_type, exc_val, exc_tb):
            return False  # Don't suppress exceptions
        mock_client.__aexit__ = AsyncMock(side_effect=mock_aexit)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)


class TestGraphQLExecutorHeaders:
    """Test header building."""

    def test_build_headers_with_auth(self, executor):
        """Test building headers with auth."""
        headers = executor._build_headers()

        assert "Authorization" in headers
        assert "Bearer ghp_test_token" in headers["Authorization"]
        assert "Content-Type" in headers

    def test_build_headers_no_auth(self, executor_no_auth):
        """Test building headers without auth."""
        headers = executor_no_auth._build_headers()

        assert "Authorization" not in headers
        assert "Content-Type" in headers

    def test_build_headers_custom_header_format(self):
        """Test parsing custom header format."""
        config = GraphQLServerConfig(
            url="https://api.example.com/graphql",
            auth=AuthConfig(
                header="X-API-Key: test-key-123"
            ),
        )
        executor = GraphQLExecutor(config)
        headers = executor._build_headers()

        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test-key-123"


class TestGraphQLExecutorResponseProcessing:
    """Test response processing."""

    def test_process_response_success(self, executor):
        """Test processing successful response."""
        data = {
            "data": {
                "user": {
                    "login": "octocat",
                    "name": "The Octocat",
                }
            }
        }

        result = executor._process_response(data, "user")

        assert result.is_error is False
        assert len(result.content) > 0
        assert result.content[0]["type"] == "text"

    def test_process_response_with_errors(self, executor):
        """Test processing response with GraphQL errors."""
        data = {
            "data": {
                "user": None
            },
            "errors": [
                {
                    "message": "User not found",
                    "path": ["user"],
                }
            ]
        }

        result = executor._process_response(data, "user")

        assert result.is_error is True

    def test_process_response_no_data_field(self, executor):
        """Test processing response without data field."""
        data = {
            "message": "OK"
        }

        result = executor._process_response(data, "user")

        assert result.is_error is False

    def test_process_response_missing_operation_result(self, executor):
        """Test processing response where operation result is missing."""
        data = {
            "data": {
                "otherField": {
                    "value": "test",
                }
            }
        }

        result = executor._process_response(data, "user")

        # Should fallback to entire data field
        assert result.is_error is False

    def test_extract_data_success(self, executor):
        """Test extracting data from response."""
        response = {
            "data": {"user": {"login": "octocat"}}
        }

        data = executor._extract_data(response)

        assert data == {"user": {"login": "octocat"}}

    def test_extract_data_missing(self, executor):
        """Test extracting data when missing."""
        response = {}

        data = executor._extract_data(response)

        assert data is None


class TestGraphQLError:
    """Test GraphQLError exception."""

    def test_init_with_errors(self):
        """Test initializing with errors."""
        errors = [
            {"message": "Error 1"},
            {"message": "Error 2"},
        ]

        error = GraphQLError(errors)

        assert error.errors == errors
        assert "Error 1" in str(error)
        assert "Error 2" in str(error)

    def test_init_with_error_missing_message(self):
        """Test initializing with errors missing message field."""
        errors = [
            {"path": ["user"]},
            {"message": "Has message"},
        ]

        error = GraphQLError(errors)

        assert "Unknown error" in str(error)
        assert "Has message" in str(error)


class TestGraphQLResponseSizeLimits:
    """Test response size limits to prevent memory exhaustion."""

    @pytest.mark.asyncio
    async def test_oversized_request_rejected(self, executor, sample_operation, sample_schema):
        """Test that oversized requests are rejected."""
        # Create variables larger than MAX_RESPONSE_SIZE
        large_variables = {
            "data": "x" * (MAX_RESPONSE_SIZE + 1)
        }

        with pytest.raises(ValueError, match="Request payload too large"):
            await executor.execute(sample_operation, large_variables, sample_schema)

    @pytest.mark.asyncio
    async def test_normal_sized_request_accepted(self, executor, sample_operation, sample_schema):
        """Test that normal-sized requests are accepted."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": {
                        "login": "octocat",
                        "name": "The Octocat",
                    }
                }
            }
        )
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'{"user": {"login": "octocat"}}'

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_oversized_response_by_content_length_rejected(self, executor, sample_operation, sample_schema):
        """Test that responses with large Content-Length header are rejected."""
        # Create a mock headers dict that behaves like a real dict
        mock_headers = {"content-length": str(MAX_RESPONSE_SIZE + 1)}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = mock_headers
        mock_response.content = b'{}'
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": {}})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        # Make __aexit__ propagate exceptions
        async def mock_aexit(exc_type, exc_val, exc_tb):
            return False  # Don't suppress exceptions
        mock_client.__aexit__ = AsyncMock(side_effect=mock_aexit)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Use try/except instead of pytest.raises to debug
            try:
                await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                # Expected error
                assert "Response too large" in str(e)

    @pytest.mark.asyncio
    async def test_oversized_response_content_rejected(self, executor, sample_operation, sample_schema):
        """Test that responses with large actual content are rejected."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        # Content larger than MAX_RESPONSE_SIZE
        mock_response.content = b'x' * (MAX_RESPONSE_SIZE + 1)
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": {}})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        # Make __aexit__ propagate exceptions
        async def mock_aexit(exc_type, exc_val, exc_tb):
            return False  # Don't suppress exceptions
        mock_client.__aexit__ = AsyncMock(side_effect=mock_aexit)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="Response content too large"):
                await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)

    @pytest.mark.asyncio
    async def test_normal_sized_response_accepted(self, executor, sample_operation, sample_schema):
        """Test that normal-sized responses are accepted."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "user": {
                        "login": "octocat",
                        "name": "The Octocat",
                    }
                }
            }
        )
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'{"user": {"login": "octocat"}}'

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await executor.execute(sample_operation, {"login": "octocat"}, sample_schema)

        assert result.is_error is False

    def test_max_response_size_constant(self):
        """Test that MAX_RESPONSE_SIZE is set to 10MB."""
        assert MAX_RESPONSE_SIZE == 10 * 1024 * 1024
