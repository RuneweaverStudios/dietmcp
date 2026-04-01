"""Tests for GraphQL introspection functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from dietmcp.graphql.introspection import (
    GraphQLIntrospector,
    INTROSPECTION_QUERY,
)
from dietmcp.models.graphql import (
    GraphQLSchema,
    GraphQLType,
    GraphQLField,
    GraphQLArgument,
    GraphQLOperation,
)


@pytest.fixture
def sample_introspection_result():
    """Sample introspection result for GitHub API."""
    return {
        "__schema": {
            "queryType": {"name": "Query"},
            "mutationType": {"name": "Mutation"},
            "types": [
                {
                    "name": "Query",
                    "kind": "OBJECT",
                    "description": "Root query type",
                    "fields": [
                        {
                            "name": "user",
                            "description": "Get a user",
                            "type": {
                                "name": "User",
                                "kind": "OBJECT",
                                "ofType": None,
                            },
                            "args": [
                                {
                                    "name": "login",
                                    "description": "User login",
                                    "type": {
                                        "name": "String",
                                        "kind": "NON_NULL",
                                        "ofType": {
                                            "name": "String",
                                            "kind": "SCALAR",
                                        },
                                    },
                                    "defaultValue": None,
                                }
                            ],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "repository",
                            "description": "Get a repository",
                            "type": {
                                "name": "Repository",
                                "kind": "OBJECT",
                                "ofType": None,
                            },
                            "args": [
                                {
                                    "name": "owner",
                                    "description": "Repository owner",
                                    "type": {
                                        "name": "String",
                                        "kind": "NON_NULL",
                                        "ofType": {
                                            "name": "String",
                                            "kind": "SCALAR",
                                        },
                                    },
                                    "defaultValue": None,
                                },
                                {
                                    "name": "name",
                                    "description": "Repository name",
                                    "type": {
                                        "name": "String",
                                        "kind": "NON_NULL",
                                        "ofType": {
                                            "name": "String",
                                            "kind": "SCALAR",
                                        },
                                    },
                                    "defaultValue": None,
                                },
                            ],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                },
                {
                    "name": "Mutation",
                    "kind": "OBJECT",
                    "description": "Root mutation type",
                    "fields": [
                        {
                            "name": "addComment",
                            "description": "Add a comment",
                            "type": {
                                "name": "Comment",
                                "kind": "OBJECT",
                                "ofType": None,
                            },
                            "args": [
                                {
                                    "name": "subjectId",
                                    "description": "Subject ID",
                                    "type": {
                                        "name": "ID",
                                        "kind": "NON_NULL",
                                        "ofType": {
                                            "name": "ID",
                                            "kind": "SCALAR",
                                        },
                                    },
                                    "defaultValue": None,
                                },
                                {
                                    "name": "body",
                                    "description": "Comment body",
                                    "type": {
                                        "name": "String",
                                        "kind": "NON_NULL",
                                        "ofType": {
                                            "name": "String",
                                            "kind": "SCALAR",
                                        },
                                    },
                                    "defaultValue": None,
                                },
                            ],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                },
                {
                    "name": "User",
                    "kind": "OBJECT",
                    "description": "A user",
                    "fields": [
                        {
                            "name": "login",
                            "description": "Username",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "email",
                            "description": "Email",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                },
                {
                    "name": "Repository",
                    "kind": "OBJECT",
                    "description": "A repository",
                    "fields": [
                        {
                            "name": "name",
                            "description": "Repository name",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "description",
                            "description": "Repository description",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                },
                {
                    "name": "Comment",
                    "kind": "OBJECT",
                    "description": "A comment",
                    "fields": [
                        {
                            "name": "id",
                            "description": "Comment ID",
                            "type": {
                                "name": "ID",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "body",
                            "description": "Comment body",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                },
                {
                    "name": "String",
                    "kind": "SCALAR",
                    "description": "String scalar",
                },
                {
                    "name": "ID",
                    "kind": "SCALAR",
                    "description": "ID scalar",
                },
            ],
        }
    }


@pytest.fixture
def introspector():
    """Create GraphQLIntrospector instance."""
    return GraphQLIntrospector()


class TestGraphQLIntrospector:
    """Test suite for GraphQLIntrospector."""

    def test_init(self):
        """Test introspector initialization."""
        introspector = GraphQLIntrospector(timeout=60.0)
        assert introspector.timeout == 60.0

    def test_init_default_timeout(self):
        """Test introspector initialization with default timeout."""
        introspector = GraphQLIntrospector()
        assert introspector.timeout == 30.0

    @pytest.mark.asyncio
    async def test_introspect_success(self, introspector, sample_introspection_result):
        """Test successful introspection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": sample_introspection_result
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            schema = await introspector.introspect("https://api.example.com/graphql")

        assert schema is not None
        assert schema.query_type_name == "Query"
        assert schema.mutation_type_name == "Mutation"
        assert len(schema.types) == 7  # Query, Mutation, User, Repository, Comment, String, ID
        assert len(schema.queries) == 2
        assert len(schema.mutations) == 1

    @pytest.mark.asyncio
    async def test_introspect_with_headers(self, introspector, sample_introspection_result):
        """Test introspection with custom headers (e.g., auth)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": sample_introspection_result
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        headers = {"Authorization": "Bearer token123"}

        with patch("httpx.AsyncClient", return_value=mock_client):
            await introspector.introspect(
                "https://api.example.com/graphql",
                headers=headers
            )

            # Verify headers were passed to the POST request
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs.get("headers") == headers

    @pytest.mark.asyncio
    async def test_introspect_network_error(self, introspector):
        """Test introspection with network error."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.ConnectError):
                await introspector.introspect("https://api.example.com/graphql")

    @pytest.mark.asyncio
    async def test_introspect_http_error(self, introspector):
        """Test introspection with HTTP error status."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await introspector.introspect("https://api.example.com/graphql")

    @pytest.mark.asyncio
    async def test_introspect_graphql_errors(self, introspector):
        """Test introspection with GraphQL errors in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [
                {"message": "Must be authenticated"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="GraphQL errors"):
                await introspector.introspect("https://api.example.com/graphql")

    @pytest.mark.asyncio
    async def test_introspect_missing_data_field(self, introspector):
        """Test introspection with missing data field."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="missing 'data' field"):
                await introspector.introspect("https://api.example.com/graphql")

    def test_parse_schema(self, introspector, sample_introspection_result):
        """Test schema parsing from introspection data."""
        schema_data = sample_introspection_result["__schema"]
        schema = introspector._parse_schema(schema_data)

        assert schema.query_type_name == "Query"
        assert schema.mutation_type_name == "Mutation"
        assert len(schema.types) == 7  # Query, Mutation, User, Repository, Comment, String, ID
        assert len(schema.queries) == 2
        assert len(schema.mutations) == 1

    def test_parse_schema_no_mutations(self, introspector):
        """Test schema parsing with no mutations."""
        schema_data = {
            "queryType": {"name": "Query"},
            # Don't include mutationType field at all
            "types": [
                {
                    "name": "Query",
                    "kind": "OBJECT",
                    "fields": [
                        {
                            "name": "hello",
                            "description": "Say hello",
                            "type": {"name": "String", "kind": "SCALAR", "ofType": None},
                            "args": [],
                            "isDeprecated": False,
                            "deprecationReason": None,
                        }
                    ],
                },
                {
                    "name": "String",
                    "kind": "SCALAR",
                },
            ],
        }

        schema = introspector._parse_schema(schema_data)

        assert schema.query_type_name == "Query"
        assert schema.mutation_type_name is None
        assert len(schema.mutations) == 0
        assert len(schema.queries) == 1

    def test_parse_type(self, introspector):
        """Test parsing a single type."""
        type_data = {
            "name": "User",
            "kind": "OBJECT",
            "description": "A user",
            "fields": [
                {
                    "name": "login",
                    "description": "Username",
                    "type": {"name": "String", "kind": "SCALAR", "ofType": None},
                    "args": [],
                    "isDeprecated": False,
                    "deprecationReason": None,
                }
            ],
        }

        graphql_type = introspector._parse_type(type_data)

        assert graphql_type.name == "User"
        assert graphql_type.kind == "OBJECT"
        assert graphql_type.description == "A user"
        assert len(graphql_type.fields) == 1
        assert "login" in graphql_type.fields

    def test_parse_type_no_fields(self, introspector):
        """Test parsing a scalar type with no fields."""
        type_data = {
            "name": "String",
            "kind": "SCALAR",
            "description": "String scalar",
        }

        graphql_type = introspector._parse_type(type_data)

        assert graphql_type.name == "String"
        assert graphql_type.kind == "SCALAR"
        assert graphql_type.fields is None

    def test_parse_field(self, introspector):
        """Test parsing a single field."""
        field_data = {
            "name": "user",
            "description": "Get a user",
            "type": {
                "name": "User",
                "kind": "OBJECT",
                "ofType": None,
            },
            "args": [
                {
                    "name": "login",
                    "description": "User login",
                    "type": {
                        "name": "String",
                        "kind": "NON_NULL",
                        "ofType": {
                            "name": "String",
                            "kind": "SCALAR",
                        },
                    },
                    "defaultValue": None,
                }
            ],
            "isDeprecated": False,
            "deprecationReason": None,
        }

        field = introspector._parse_field(field_data)

        assert field.name == "user"
        assert field.description == "Get a user"
        assert field.type_name == "User"  # Returns the actual type, not wrapped
        assert field.type_kind == "OBJECT"
        assert len(field.args) == 1
        assert field.is_deprecated is False

    def test_parse_field_deprecated(self, introspector):
        """Test parsing a deprecated field."""
        field_data = {
            "name": "oldField",
            "description": "Old deprecated field",
            "type": {"name": "String", "kind": "SCALAR", "ofType": None},
            "args": [],
            "isDeprecated": True,
            "deprecationReason": "Use newField instead",
        }

        field = introspector._parse_field(field_data)

        assert field.is_deprecated is True
        assert field.deprecation_reason == "Use newField instead"

    def test_parse_arg(self, introspector):
        """Test parsing a single argument."""
        arg_data = {
            "name": "login",
            "description": "User login",
            "type": {
                "name": "String",
                "kind": "NON_NULL",
                "ofType": {
                    "name": "String",
                    "kind": "SCALAR",
                },
            },
            "defaultValue": None,
        }

        arg = introspector._parse_arg(arg_data)

        assert arg.name == "login"
        assert arg.description == "User login"
        assert arg.type_name == "String"
        assert arg.type_kind == "SCALAR"
        assert arg.default_value is None

    def test_parse_arg_with_default(self, introspector):
        """Test parsing argument with default value."""
        arg_data = {
            "name": "limit",
            "description": "Result limit",
            "type": {
                "name": "Int",
                "kind": "SCALAR",
                "ofType": None,
            },
            "defaultValue": "10",
        }

        arg = introspector._parse_arg(arg_data)

        assert arg.name == "limit"
        assert arg.default_value == "10"

    def test_extract_type_info_scalar(self, introspector):
        """Test type info extraction for scalar type."""
        type_data = {
            "name": "String",
            "kind": "SCALAR",
            "ofType": None,
        }

        info = introspector._extract_type_info(type_data)

        assert info["name"] == "String"
        assert info["kind"] == "SCALAR"

    def test_extract_type_info_non_null(self, introspector):
        """Test type info extraction for NON_NULL wrapper."""
        type_data = {
            "name": None,
            "kind": "NON_NULL",
            "ofType": {
                "name": "String",
                "kind": "SCALAR",
                "ofType": None,
            },
        }

        info = introspector._extract_type_info(type_data)

        assert info["name"] == "String"
        assert info["kind"] == "SCALAR"

    def test_extract_type_info_list(self, introspector):
        """Test type info extraction for LIST wrapper."""
        type_data = {
            "name": None,
            "kind": "LIST",
            "ofType": {
                "name": "String",
                "kind": "SCALAR",
                "ofType": None,
            },
        }

        info = introspector._extract_type_info(type_data)

        assert info["name"] == "String"
        assert info["kind"] == "SCALAR"

    def test_extract_type_info_nested_wrappers(self, introspector):
        """Test type info extraction with nested wrappers (NON_NULL LIST)."""
        type_data = {
            "name": None,
            "kind": "NON_NULL",
            "ofType": {
                "name": None,
                "kind": "LIST",
                "ofType": {
                    "name": "String",
                    "kind": "SCALAR",
                    "ofType": None,
                },
            },
        }

        info = introspector._extract_type_info(type_data)

        assert info["name"] == "String"
        assert info["kind"] == "SCALAR"

    def test_extract_type_info_unknown_type(self, introspector):
        """Test type info extraction for unknown type."""
        type_data = {
            "name": None,
            "kind": "UNKNOWN",
            "ofType": None,
        }

        info = introspector._extract_type_info(type_data)

        assert info["name"] == "Unknown"
        assert info["kind"] == "UNKNOWN"

    def test_extract_operations(self, introspector, sample_introspection_result):
        """Test extracting operations from root type."""
        schema_data = sample_introspection_result["__schema"]
        types = {}
        for type_data in schema_data["types"]:
            graphql_type = introspector._parse_type(type_data)
            types[graphql_type.name] = graphql_type

        queries = introspector._extract_operations("Query", types)

        assert len(queries) == 2
        assert queries[0].name == "user"
        assert queries[1].name == "repository"

    def test_extract_operations_no_root_type(self, introspector):
        """Test extracting operations when root type doesn't exist."""
        operations = introspector._extract_operations("NonExistent", {})
        assert operations == []

    def test_extract_operations_root_type_no_fields(self, introspector):
        """Test extracting operations when root type has no fields."""
        types = {
            "EmptyQuery": GraphQLType(
                name="EmptyQuery",
                kind="OBJECT",
                description=None,
                fields=None,
            )
        }

        operations = introspector._extract_operations("EmptyQuery", types)
        assert operations == []

    def test_extract_queries(self, introspector):
        """Test extracting queries from schema."""
        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name="Mutation",
            types={},
            queries=[
                GraphQLOperation(
                    name="user",
                    description="Get user",
                    field=GraphQLField(
                        name="user",
                        description="Get user",
                        type_name="User",
                        type_kind="OBJECT",
                        args=[],
                    ),
                )
            ],
            mutations=[],
        )

        queries = introspector.extract_queries(schema)

        assert len(queries) == 1
        assert queries[0].name == "user"

    def test_extract_mutations(self, introspector):
        """Test extracting mutations from schema."""
        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name="Mutation",
            types={},
            queries=[],
            mutations=[
                GraphQLOperation(
                    name="addComment",
                    description="Add comment",
                    field=GraphQLField(
                        name="addComment",
                        description="Add comment",
                        type_name="Comment",
                        type_kind="OBJECT",
                        args=[],
                    ),
                )
            ],
        )

        mutations = introspector.extract_mutations(schema)

        assert len(mutations) == 1
        assert mutations[0].name == "addComment"

    def test_introspection_query_constant(self):
        """Test that INTROSPECTION_QUERY is a valid GraphQL query."""
        assert "query IntrospectionQuery" in INTROSPECTION_QUERY
        assert "__schema" in INTROSPECTION_QUERY
        assert "queryType" in INTROSPECTION_QUERY
        assert "mutationType" in INTROSPECTION_QUERY
        assert "types" in INTROSPECTION_QUERY


class TestGraphQLIntrospectionEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_introspect_timeout(self, introspector):
        """Test introspection timeout."""
        introspector.timeout = 0.001  # Very short timeout

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.TimeoutException):
                await introspector.introspect("https://api.example.com/graphql")

    def test_parse_empty_schema(self, introspector):
        """Test parsing empty schema."""
        schema = introspector._parse_schema({})

        assert schema.query_type_name is None
        assert schema.mutation_type_name is None
        assert len(schema.types) == 0
        assert len(schema.queries) == 0
        assert len(schema.mutations) == 0

    def test_parse_schema_no_types(self, introspector):
        """Test parsing schema with no types field."""
        schema_data = {
            "queryType": {"name": "Query"},
            # Don't include mutationType or types fields
        }

        schema = introspector._parse_schema(schema_data)

        assert len(schema.types) == 0
        assert len(schema.queries) == 0

    def test_parse_field_no_args(self, introspector):
        """Test parsing field with no arguments."""
        field_data = {
            "name": "version",
            "description": "API version",
            "type": {"name": "String", "kind": "SCALAR", "ofType": None},
            "args": [],
            "isDeprecated": False,
            "deprecationReason": None,
        }

        field = introspector._parse_field(field_data)

        assert len(field.args) == 0

    def test_extract_type_info_no_oftype(self):
        """Test type info extraction when ofType is missing."""
        introspector = GraphQLIntrospector()
        type_data = {
            "name": "CustomType",
            "kind": "OBJECT",
        }

        info = introspector._extract_type_info(type_data)

        assert info["name"] == "CustomType"
        assert info["kind"] == "OBJECT"
