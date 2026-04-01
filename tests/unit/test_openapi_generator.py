"""Comprehensive unit tests for OpenAPI tool generator.

Tests tool generation from endpoints, signature generation (standard and ultra-compact),
parameter mapping, request body handling, and enum/array/object types.
"""

from __future__ import annotations

import pytest

from dietmcp.openapi.generator import (
    OpenAPIToolGenerator,
    generate_signature,
    generate_operation_id,
    OperationIDStrategy,
    _json_type_to_hint,
)
from dietmcp.models.openapi import OpenAPIEndpoint, OpenAPIParameter, OpenAPISpec
from dietmcp.models.tool import ToolDefinition


@pytest.fixture
def sample_endpoint():
    """Sample endpoint for testing."""
    return OpenAPIEndpoint(
        path="/users/{userId}",
        method="GET",
        operation_id="getUserById",
        summary="Get user by ID",
        description="Retrieve a single user",
        parameters=[
            OpenAPIParameter(
                name="userId",
                in_="path",
                description="User ID",
                required=True,
                schema_={"type": "integer"}
            ),
            OpenAPIParameter(
                name="verbose",
                in_="query",
                description="Verbose output",
                required=False,
                schema_={"type": "boolean"}
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=["users"],
    )


@pytest.fixture
def endpoint_with_request_body():
    """Endpoint with request body for testing."""
    return OpenAPIEndpoint(
        path="/users",
        method="POST",
        operation_id="createUser",
        summary="Create a new user",
        parameters=[
            OpenAPIParameter(
                name="X-Auth-Token",
                in_="header",
                required=True,
                schema_={"type": "string"}
            )
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
                            "email": {"type": "string", "format": "email"},
                            "age": {"type": "integer"}
                        },
                        "required": ["name", "email"]
                    }
                }
            }
        },
        responses={"201": {"description": "Created"}},
        tags=["users"],
    )


@pytest.fixture
def endpoint_with_enums():
    """Endpoint with enum parameters."""
    return OpenAPIEndpoint(
        path="/items",
        method="GET",
        operation_id="getItems",
        summary="Get items",
        parameters=[
            OpenAPIParameter(
                name="status",
                in_="query",
                schema_={
                    "type": "string",
                    "enum": ["active", "inactive", "pending"]
                }
            ),
            OpenAPIParameter(
                name="sort",
                in_="query",
                schema_={
                    "type": "string",
                    "enum": ["name", "date", "price"]
                }
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def endpoint_with_arrays():
    """Endpoint with array parameters."""
    return OpenAPIEndpoint(
        path="/items",
        method="GET",
        operation_id="filterItems",
        summary="Filter items",
        parameters=[
            OpenAPIParameter(
                name="tags",
                in_="query",
                schema_={
                    "type": "array",
                    "items": {"type": "string"}
                }
            ),
            OpenAPIParameter(
                name="ids",
                in_="query",
                schema_={
                    "type": "array",
                    "items": {"type": "integer"}
                }
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def endpoint_with_objects():
    """Endpoint with object parameters."""
    return OpenAPIEndpoint(
        path="/search",
        method="POST",
        operation_id="searchItems",
        summary="Search items",
        request_body={
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "filter": {
                                "type": "object",
                                "properties": {
                                    "category": {"type": "string"},
                                    "price_range": {
                                        "type": "object",
                                        "properties": {
                                            "min": {"type": "number"},
                                            "max": {"type": "number"}
                                        }
                                    }
                                }
                            },
                            "pagination": {
                                "type": "object",
                                "properties": {
                                    "page": {"type": "integer"},
                                    "limit": {"type": "integer"}
                                }
                            }
                        }
                    }
                }
            }
        },
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def endpoint_without_operation_id():
    """Endpoint without operationId to test auto-generation."""
    return OpenAPIEndpoint(
        path="/api/v1/users/{userId}/posts/{postId}",
        method="GET",
        operation_id=None,
        parameters=[
            OpenAPIParameter(
                name="userId",
                in_="path",
                required=True,
                schema_={"type": "integer"}
            ),
            OpenAPIParameter(
                name="postId",
                in_="path",
                required=True,
                schema_={"type": "integer"}
            ),
        ],
        request_body=None,
        responses={"200": {"description": "OK"}},
        tags=[],
    )


@pytest.fixture
def sample_spec():
    """Sample spec for testing."""
    return OpenAPISpec(
        title="Sample API",
        version="1.0.0",
        description="A sample API",
        servers=[{"url": "https://api.example.com"}],
        endpoints=[],
        security_schemes={},
        components_schemas={},
    )


class TestGenerateTools:
    """Test tool generation from specs."""

    def test_generate_tools_from_spec(self, sample_endpoint, sample_spec):
        spec_with_endpoint = sample_spec.model_copy(
            update={"endpoints": [sample_endpoint]}
        )

        generator = OpenAPIToolGenerator()
        tools = generator.generate_tools(spec_with_endpoint, "sample-api")

        assert len(tools) == 1
        assert tools[0].name == "getUserById"
        assert tools[0].server_name == "sample-api"

    def test_generate_multiple_tools(self, sample_spec):
        endpoints = [
            OpenAPIEndpoint(
                path="/users",
                method="GET",
                operation_id="getUsers",
                parameters=[],
                request_body=None,
                responses={},
                tags=[],
            ),
            OpenAPIEndpoint(
                path="/users",
                method="POST",
                operation_id="createUser",
                parameters=[],
                request_body={
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"}
                        }
                    }
                },
                responses={},
                tags=[],
            ),
            OpenAPIEndpoint(
                path="/users/{id}",
                method="DELETE",
                operation_id="deleteUser",
                parameters=[],
                request_body=None,
                responses={},
                tags=[],
            ),
        ]

        spec_with_endpoints = sample_spec.model_copy(
            update={"endpoints": endpoints}
        )

        generator = OpenAPIToolGenerator()
        tools = generator.generate_tools(spec_with_endpoints, "users-api")

        assert len(tools) == 3
        tool_names = {t.name for t in tools}
        assert tool_names == {"getUsers", "createUser", "deleteUser"}

    def test_generate_tools_with_ultra_compact(self, sample_endpoint, sample_spec):
        spec_with_endpoint = sample_spec.model_copy(
            update={"endpoints": [sample_endpoint]}
        )

        generator = OpenAPIToolGenerator()
        tools_standard = generator.generate_tools(spec_with_endpoint, "api", ultra_compact=False)
        tools_compact = generator.generate_tools(spec_with_endpoint, "api", ultra_compact=True)

        # Both should generate tools, but signature format differs
        assert len(tools_standard) == 1
        assert len(tools_compact) == 1


class TestGenerateTool:
    """Test single tool generation."""

    def test_generate_tool_basic(self, sample_endpoint):
        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(sample_endpoint, "test-api", ultra_compact=False)

        assert isinstance(tool, ToolDefinition)
        assert tool.name == "getUserById"
        assert tool.description == "Get user by ID"
        assert tool.server_name == "test-api"
        assert "userId" in tool.input_schema["properties"]
        assert "verbose" in tool.input_schema["properties"]

    def test_tool_description_fallback(self):
        """Test description fallback when summary is missing."""
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="GET",
            operation_id="getUsers",
            summary=None,
            description=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint, "api", ultra_compact=False)

        assert tool.description == "GET /users"

    def test_tool_description_with_description_only(self):
        """Test description when only description field is present."""
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="GET",
            operation_id="getUsers",
            summary=None,
            description="List all users",
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint, "api", ultra_compact=False)

        assert tool.description == "List all users"

    def test_generate_tool_with_auto_operation_id(self, endpoint_without_operation_id):
        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint_without_operation_id, "api", ultra_compact=False)

        # Should auto-generate operation ID
        assert tool.name is not None
        assert "get" in tool.name.lower()
        # Generated ID should be based on path (case-insensitive check)
        tool_name_lower = tool.name.lower()
        assert "api" in tool_name_lower or "v1" in tool_name_lower or "users" in tool_name_lower


class TestGenerateOperationId:
    """Test operation ID generation."""

    def test_generate_operation_id_simple_path(self):
        generator = OpenAPIToolGenerator()
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        operation_id = generator._generate_operation_id(endpoint)
        assert operation_id == "getUsers"

    def test_generate_operation_id_with_path_params(self):
        generator = OpenAPIToolGenerator()
        endpoint = OpenAPIEndpoint(
            path="/users/{id}/posts/{postId}",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        operation_id = generator._generate_operation_id(endpoint)
        assert operation_id == "getUsersPosts"

    def test_generate_operation_id_nested_path(self):
        generator = OpenAPIToolGenerator()
        endpoint = OpenAPIEndpoint(
            path="/api/v1/users/{id}",
            method="POST",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        operation_id = generator._generate_operation_id(endpoint)
        # Should preserve api/v1 structure in camelCase
        assert "post" in operation_id.lower()
        assert "Api" in operation_id or "V1" in operation_id or "Users" in operation_id

    def test_generate_operation_id_root_path(self):
        generator = OpenAPIToolGenerator()
        endpoint = OpenAPIEndpoint(
            path="/",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        operation_id = generator._generate_operation_id(endpoint)
        # Root path generates "getRoot" (or similar)
        assert "get" in operation_id.lower()

    def test_generate_operation_id_trailing_slash(self):
        generator = OpenAPIToolGenerator()
        endpoint = OpenAPIEndpoint(
            path="/users/",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        operation_id = generator._generate_operation_id(endpoint)
        assert operation_id == "getUsers"

    def test_generate_operation_id_all_methods(self):
        generator = OpenAPIToolGenerator()
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]

        for method in methods:
            endpoint = OpenAPIEndpoint(
                path="/items",
                method=method,
                operation_id=None,
                parameters=[],
                request_body=None,
                responses={},
                tags=[],
            )

            operation_id = generator._generate_operation_id(endpoint)
            assert operation_id.lower().startswith(method.lower())


class TestBuildInputSchema:
    """Test input schema building."""

    def test_build_input_schema_with_parameters(self, sample_endpoint):
        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(sample_endpoint)

        assert schema["type"] == "object"
        assert "userId" in schema["properties"]
        assert "verbose" in schema["properties"]
        assert "userId" in schema["required"]
        assert "verbose" not in schema["required"]

    def test_build_input_schema_with_request_body(self, endpoint_with_request_body):
        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint_with_request_body)

        assert "request_body" in schema["properties"]
        assert "X-Auth-Token" in schema["properties"]
        assert "request_body" in schema["required"]

        # Check request body schema structure
        body_schema = schema["properties"]["request_body"]
        assert body_schema["type"] == "object"
        assert "properties" in body_schema
        assert "name" in body_schema["properties"]
        assert "email" in body_schema["properties"]

    def test_build_input_schema_empty(self):
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="GET",
            operation_id="test",
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema["required"] == []


class TestConvertParamSchema:
    """Test parameter schema conversion."""

    def test_convert_param_with_schema(self):
        param = OpenAPIParameter(
            name="limit",
            in_="query",
            schema_={"type": "integer", "minimum": 1, "maximum": 100},
            description="Max items",
            required=False,
        )

        generator = OpenAPIToolGenerator()
        schema = generator._convert_param_schema(param)

        assert schema["type"] == "integer"
        assert schema["minimum"] == 1
        assert schema["maximum"] == 100
        assert schema["description"] == "Max items"

    def test_convert_param_without_schema(self):
        param = OpenAPIParameter(
            name="query",
            in_="query",
            schema_=None,
            description="Search query",
        )

        generator = OpenAPIToolGenerator()
        schema = generator._convert_param_schema(param)

        assert schema["type"] == "string"
        assert schema["description"] == "Search query"

    def test_convert_param_with_example(self):
        param = OpenAPIParameter(
            name="status",
            in_="query",
            schema_={"type": "string"},
            example="active",
        )

        generator = OpenAPIToolGenerator()
        schema = generator._convert_param_schema(param)

        assert schema["example"] == "active"

    def test_convert_param_without_type_in_schema(self):
        param = OpenAPIParameter(
            name="param",
            in_="query",
            schema_={"description": "No type specified"},
        )

        generator = OpenAPIToolGenerator()
        schema = generator._convert_param_schema(param)

        assert schema["type"] == "string"


class TestExtractBodySchema:
    """Test request body schema extraction."""

    def test_extract_json_body(self, endpoint_with_request_body):
        generator = OpenAPIToolGenerator()
        schema = generator._extract_body_schema(endpoint_with_request_body.request_body)

        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_extract_body_with_description(self):
        request_body = {
            "description": "User data",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {"name": {"type": "string"}}}
                }
            },
        }

        generator = OpenAPIToolGenerator()
        schema = generator._extract_body_schema(request_body)

        assert schema["description"] == "User data"

    def test_extract_body_non_json_content(self):
        request_body = {
            "content": {
                "text/plain": {
                    "schema": {"type": "string"}
                }
            }
        }

        generator = OpenAPIToolGenerator()
        schema = generator._extract_body_schema(request_body)

        assert schema is not None
        assert schema["type"] == "string"

    def test_extract_body_no_schema(self):
        request_body = {
            "content": {
                "application/json": {}
            }
        }

        generator = OpenAPIToolGenerator()
        schema = generator._extract_body_schema(request_body)

        assert schema is None


class TestGenerateSignature:
    """Test signature generation."""

    def test_generate_signature_basic(self, sample_endpoint):
        signature = generate_signature(sample_endpoint, ultra_compact=False)

        assert "getUserById" in signature
        assert "userId:" in signature
        assert "?" in signature  # Optional parameter marker

    def test_generate_signature_ultra_compact(self, sample_endpoint):
        signature = generate_signature(sample_endpoint, ultra_compact=True)

        assert "getUserById" in signature
        # Ultra-compact should have '?' suffix for optional params
        assert "?" in signature

    def test_generate_signature_with_request_body(self, endpoint_with_request_body):
        signature = generate_signature(endpoint_with_request_body, ultra_compact=False)

        assert "createUser" in signature
        assert "request_body:" in signature
        assert "X-Auth-Token:" in signature

    def test_generate_signature_with_enums(self, endpoint_with_enums):
        signature = generate_signature(endpoint_with_enums, ultra_compact=False)

        assert "getItems" in signature
        # Enums should show values
        assert "active" in signature or "inactive" in signature

    def test_generate_signature_with_arrays(self, endpoint_with_arrays):
        signature = generate_signature(endpoint_with_arrays, ultra_compact=False)

        assert "filterItems" in signature
        assert "list" in signature or "[]" in signature

    def test_generate_signature_no_params(self):
        endpoint = OpenAPIEndpoint(
            path="/health",
            method="GET",
            operation_id="healthCheck",
            parameters=[],
            request_body=None,
            responses={"200": {"description": "OK"}},
            tags=[],
        )

        signature = generate_signature(endpoint, ultra_compact=False)
        assert "healthCheck()" in signature


class TestJsonTypeToHint:
    """Test JSON type to type hint conversion."""

    def test_primitive_types(self):
        generator = OpenAPIToolGenerator()

        # String
        assert _json_type_to_hint({"type": "string"}, ultra_compact=False) == "str"
        assert _json_type_to_hint({"type": "string"}, ultra_compact=True) == ""

        # Integer
        assert _json_type_to_hint({"type": "integer"}, ultra_compact=False) == "int"
        assert _json_type_to_hint({"type": "integer"}, ultra_compact=True) == ""

        # Number
        assert _json_type_to_hint({"type": "number"}, ultra_compact=False) == "float"
        assert _json_type_to_hint({"type": "number"}, ultra_compact=True) == ""

        # Boolean
        assert _json_type_to_hint({"type": "boolean"}, ultra_compact=False) == "bool"
        assert _json_type_to_hint({"type": "boolean"}, ultra_compact=True) == ""

    def test_enum_type(self):
        schema = {
            "type": "string",
            "enum": ["active", "inactive", "pending"]
        }

        hint = _json_type_to_hint(schema, ultra_compact=False)
        assert "active" in hint
        assert "inactive" in hint
        assert "|" in hint

        # Ultra-compact should still show enums
        hint_compact = _json_type_to_hint(schema, ultra_compact=True)
        assert "active" in hint_compact

    def test_enum_truncated(self):
        schema = {
            "type": "string",
            "enum": ["a", "b", "c", "d", "e", "f", "g"]
        }

        hint = _json_type_to_hint(schema, ultra_compact=False)
        assert "..." in hint  # Truncated indicator

    def test_array_type(self):
        schema = {
            "type": "array",
            "items": {"type": "string"}
        }

        hint = _json_type_to_hint(schema, ultra_compact=False)
        assert hint == "list[str]"

        hint_compact = _json_type_to_hint(schema, ultra_compact=True)
        assert hint_compact == "[str]"

    def test_nested_array_type(self):
        schema = {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "integer"}
            }
        }

        hint = _json_type_to_hint(schema, ultra_compact=False)
        assert "list" in hint.lower()

    def test_object_type(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"}
            }
        }

        hint = _json_type_to_hint(schema, ultra_compact=False)
        assert hint == "dict"

        hint_compact = _json_type_to_hint(schema, ultra_compact=True)
        # Ultra-compact should show field names
        assert "name" in hint_compact
        assert "age" in hint_compact

    def test_empty_object_type(self):
        schema = {"type": "object"}

        hint = _json_type_to_hint(schema, ultra_compact=False)
        assert hint == "dict"

        hint_compact = _json_type_to_hint(schema, ultra_compact=True)
        assert hint_compact == "{}"

    def test_unknown_type(self):
        hint = _json_type_to_hint({"type": "unknown"}, ultra_compact=False)
        assert hint == "unknown"


class TestParameterMapping:
    """Test parameter mapping in various scenarios."""

    def test_all_parameter_locations(self):
        endpoint = OpenAPIEndpoint(
            path="/items/{itemId}",
            method="POST",
            operation_id="updateItem",
            parameters=[
                OpenAPIParameter(name="itemId", in_="path", required=True, schema_={"type": "string"}),
                OpenAPIParameter(name="query", in_="query", required=False, schema_={"type": "string"}),
                OpenAPIParameter(name="X-Header", in_="header", required=True, schema_={"type": "string"}),
                OpenAPIParameter(name="session", in_="cookie", required=False, schema_={"type": "string"}),
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        # All parameters should be in input schema
        assert "itemId" in schema["properties"]
        assert "query" in schema["properties"]
        assert "X-Header" in schema["properties"]
        assert "session" in schema["properties"]

        # Required parameters
        assert "itemId" in schema["required"]
        assert "X-Header" in schema["required"]
        assert "query" not in schema["required"]
        assert "session" not in schema["required"]

    def test_parameter_with_complex_schema(self):
        endpoint = OpenAPIEndpoint(
            path="/items",
            method="GET",
            operation_id="getItems",
            parameters=[
                OpenAPIParameter(
                    name="filter",
                    in_="query",
                    schema_={
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "value": {"type": "string"}
                        }
                    }
                ),
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        assert "filter" in schema["properties"]
        filter_schema = schema["properties"]["filter"]
        assert filter_schema["type"] == "object"


class TestRequestBodyHandling:
    """Test request body handling in various scenarios."""

    def test_post_request_body_required(self, endpoint_with_request_body):
        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint_with_request_body)

        assert "request_body" in schema["required"]

    def test_put_request_body_required(self):
        endpoint = OpenAPIEndpoint(
            path="/items/{id}",
            method="PUT",
            operation_id="updateItem",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    }
                }
            },
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        assert "request_body" in schema["required"]

    def test_patch_request_body_required(self):
        endpoint = OpenAPIEndpoint(
            path="/items/{id}",
            method="PATCH",
            operation_id="patchItem",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    }
                }
            },
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        assert "request_body" in schema["required"]

    def test_get_request_body_not_required(self):
        endpoint = OpenAPIEndpoint(
            path="/items",
            method="GET",
            operation_id="getItems",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    }
                }
            },
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        # GET typically doesn't require request body
        assert "request_body" not in schema["required"]

    def test_request_body_optional(self):
        endpoint = OpenAPIEndpoint(
            path="/items",
            method="POST",
            operation_id="createItem",
            parameters=[],
            request_body={
                "required": False,
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    }
                }
            },
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        # Even if marked optional, POST defaults to required
        # (this is the current behavior)
        assert "request_body" in schema["properties"]


class TestEnumArrayObjectTypes:
    """Test handling of complex parameter types."""

    def test_enum_parameter(self, endpoint_with_enums):
        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint_with_enums)

        status_param = schema["properties"]["status"]
        assert "enum" in status_param
        assert "active" in status_param["enum"]

    def test_array_parameter(self, endpoint_with_arrays):
        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint_with_arrays)

        tags_param = schema["properties"]["tags"]
        assert tags_param["type"] == "array"
        assert "items" in tags_param

    def test_nested_array(self):
        endpoint = OpenAPIEndpoint(
            path="/items",
            method="GET",
            operation_id="getItems",
            parameters=[
                OpenAPIParameter(
                    name="matrix",
                    in_="query",
                    schema_={
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "integer"}
                        }
                    }
                )
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        matrix_param = schema["properties"]["matrix"]
        assert matrix_param["type"] == "array"

    def test_object_parameter(self, endpoint_with_objects):
        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint_with_objects)

        assert "request_body" in schema["properties"]
        body_schema = schema["properties"]["request_body"]
        assert body_schema["type"] == "object"
        assert "properties" in body_schema

    def test_combined_types(self):
        endpoint = OpenAPIEndpoint(
            path="/items",
            method="GET",
            operation_id="getItems",
            parameters=[
                OpenAPIParameter(
                    name="status",
                    in_="query",
                    schema_={"type": "string", "enum": ["a", "b"]}
                ),
                OpenAPIParameter(
                    name="tags",
                    in_="query",
                    schema_={"type": "array", "items": {"type": "string"}}
                ),
                OpenAPIParameter(
                    name="filter",
                    in_="query",
                    schema_={
                        "type": "object",
                        "properties": {"field": {"type": "string"}}
                    }
                ),
            ],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        # All types should be present
        assert "enum" in schema["properties"]["status"]
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["filter"]["type"] == "object"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_endpoint_with_no_description_fields(self):
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="GET",
            operation_id="test",
            summary=None,
            description=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint, "api", ultra_compact=False)

        # Should fallback to method + path
        assert tool.description == "GET /test"

    def test_parameter_without_name(self):
        param = OpenAPIParameter(
            name="",
            in_="query",
            schema_={"type": "string"}
        )

        generator = OpenAPIToolGenerator()
        schema = generator._convert_param_schema(param)

        # Should handle empty name gracefully
        assert schema["type"] == "string"

    def test_request_body_with_no_content(self):
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="POST",
            operation_id="test",
            parameters=[],
            request_body={},
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._build_input_schema(endpoint)

        # Should not crash on empty request body
        assert "request_body" not in schema["properties"]

    def test_multiple_content_types(self):
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="POST",
            operation_id="test",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    },
                    "application/xml": {
                        "schema": {"type": "string"}
                    }
                }
            },
            responses={},
            tags=[],
        )

        generator = OpenAPIToolGenerator()
        schema = generator._extract_body_schema(endpoint.request_body)

        # Should prefer JSON
        assert schema is not None
        assert schema["type"] == "object"


class TestOperationIDStrategies:
    """Test operation ID generation strategies."""

    def test_auto_strategy_with_existing_operation_id(self):
        """AUTO strategy should use existing operationId from spec."""
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="GET",
            operation_id="getUserById",
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.AUTO)
        assert result == "getUserById"

    def test_auto_strategy_without_operation_id(self):
        """AUTO strategy should generate camelCase when no operationId exists."""
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.AUTO)
        assert result == "getUsers"

    def test_path_method_strategy(self):
        """PATH_METHOD strategy: {path}_{method}"""
        endpoint = OpenAPIEndpoint(
            path="/api/v1/users/{id}",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.PATH_METHOD)
        assert result == "api_v1_users_get"

    def test_path_method_strategy_root(self):
        """PATH_METHOD strategy with root path."""
        endpoint = OpenAPIEndpoint(
            path="/",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.PATH_METHOD)
        assert result == "get"

    def test_path_lower_strategy(self):
        """PATH_LOWER strategy: lowercase with underscores, no method suffix."""
        endpoint = OpenAPIEndpoint(
            path="/api/v1/users/{id}",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.PATH_LOWER)
        assert result == "api_v1_users"

    def test_camel_case_strategy_simple(self):
        """CAMEL_CASE strategy: method + capitalized path parts."""
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE)
        assert result == "getUsers"

    def test_camel_case_strategy_with_path_params(self):
        """CAMEL_CASE strategy should remove path parameters."""
        endpoint = OpenAPIEndpoint(
            path="/users/{id}/posts/{postId}",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE)
        assert result == "getUsersPosts"

    def test_camel_case_strategy_nested_path(self):
        """CAMEL_CASE strategy with nested path."""
        endpoint = OpenAPIEndpoint(
            path="/api/v1/users/{id}",
            method="POST",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE)
        assert result == "postApiV1Users"

    def test_snake_case_strategy(self):
        """SNAKE_CASE strategy: lowercase with underscores, keeps parameter names."""
        endpoint = OpenAPIEndpoint(
            path="/api/v1/users/{id}",
            method="POST",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.SNAKE_CASE)
        assert result == "api_v1_users_id"

    def test_kebab_case_strategy(self):
        """KEBAB_CASE strategy: lowercase with hyphens."""
        endpoint = OpenAPIEndpoint(
            path="/api/v1/users/{id}",
            method="POST",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.KEBAB_CASE)
        assert result == "api-v1-users"

    def test_all_strategies_with_same_endpoint(self):
        """All strategies should produce valid (different) operation IDs."""
        endpoint = OpenAPIEndpoint(
            path="/users/{id}/posts",
            method="GET",
            operation_id="customOpId",
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        results = {
            "auto": generate_operation_id(endpoint, OperationIDStrategy.AUTO),
            "path_method": generate_operation_id(endpoint, OperationIDStrategy.PATH_METHOD),
            "path_lower": generate_operation_id(endpoint, OperationIDStrategy.PATH_LOWER),
            "camel_case": generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE),
            "snake_case": generate_operation_id(endpoint, OperationIDStrategy.SNAKE_CASE),
            "kebab_case": generate_operation_id(endpoint, OperationIDStrategy.KEBAB_CASE),
        }

        # AUTO should use the existing operationId
        assert results["auto"] == "customOpId"

        # Each strategy should produce a different result
        assert len(set(results.values())) == len(results)

        # All should be valid Python identifiers
        for strategy, op_id in results.items():
            assert op_id, f"{strategy} produced empty operation ID"
            assert op_id.replace("_", "").replace("-", "").isalnum(), (
                f"{strategy} produced invalid identifier: {op_id}"
            )

    def test_strategies_with_trailing_slash(self):
        """Strategies should handle trailing slashes correctly."""
        endpoint = OpenAPIEndpoint(
            path="/users/",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        assert generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE) == "getUsers"
        assert generate_operation_id(endpoint, OperationIDStrategy.SNAKE_CASE) == "users"
        assert generate_operation_id(endpoint, OperationIDStrategy.KEBAB_CASE) == "users"

    def test_strategies_with_empty_path_segments(self):
        """Strategies should handle multiple consecutive slashes."""
        endpoint = OpenAPIEndpoint(
            path="//users//{id}//",
            method="POST",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        )

        result = generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE)
        assert "post" in result.lower()
        assert "users" in result.lower()


class TestGeneratorWithOperationIDStrategy:
    """Test OpenAPIToolGenerator with different operation ID strategies."""

    def test_generator_with_auto_strategy(self, sample_endpoint, sample_spec):
        """Generator with AUTO strategy should respect existing operationId."""
        spec_with_endpoint = sample_spec.model_copy(
            update={"endpoints": [sample_endpoint]}
        )

        generator = OpenAPIToolGenerator(operation_id_strategy=OperationIDStrategy.AUTO)
        tools = generator.generate_tools(spec_with_endpoint, "test-api")

        assert len(tools) == 1
        assert tools[0].name == "getUserById"

    def test_generator_with_snake_case_strategy(self, sample_spec):
        """Generator with SNAKE_CASE strategy."""
        endpoint = OpenAPIEndpoint(
            path="/users/{userId}",
            method="GET",
            operation_id="getUserById",  # Should be ignored
            summary="Get user by ID",
            parameters=[
                OpenAPIParameter(
                    name="userId",
                    in_="path",
                    required=True,
                    schema_={"type": "integer"}
                )
            ],
            request_body=None,
            responses={"200": {"description": "OK"}},
            tags=[],
        )

        spec_with_endpoint = sample_spec.model_copy(
            update={"endpoints": [endpoint]}
        )

        generator = OpenAPIToolGenerator(operation_id_strategy=OperationIDStrategy.SNAKE_CASE)
        tools = generator.generate_tools(spec_with_endpoint, "test-api")

        assert len(tools) == 1
        # SNAKE_CASE keeps parameter names: /users/{userId} -> users_userid
        assert tools[0].name == "users_userid"

    def test_generator_with_camel_case_strategy(self, sample_spec):
        """Generator with CAMEL_CASE strategy."""
        endpoint = OpenAPIEndpoint(
            path="/users/{userId}",
            method="GET",
            operation_id=None,
            summary="Get user by ID",
            parameters=[
                OpenAPIParameter(
                    name="userId",
                    in_="path",
                    required=True,
                    schema_={"type": "integer"}
                )
            ],
            request_body=None,
            responses={"200": {"description": "OK"}},
            tags=[],
        )

        spec_with_endpoint = sample_spec.model_copy(
            update={"endpoints": [endpoint]}
        )

        generator = OpenAPIToolGenerator(operation_id_strategy=OperationIDStrategy.CAMEL_CASE)
        tools = generator.generate_tools(spec_with_endpoint, "test-api")

        assert len(tools) == 1
        assert tools[0].name == "getUsers"

    def test_generator_default_strategy(self, sample_endpoint, sample_spec):
        """Generator should default to AUTO strategy."""
        spec_with_endpoint = sample_spec.model_copy(
            update={"endpoints": [sample_endpoint]}
        )

        # Create generator without specifying strategy
        generator = OpenAPIToolGenerator()
        tools = generator.generate_tools(spec_with_endpoint, "test-api")

        assert len(tools) == 1
        # Should use existing operationId (AUTO behavior)
        assert tools[0].name == "getUserById"


class TestGenerateSignatureWithStrategy:
    """Test generate_signature function with operation ID strategies."""

    def test_signature_with_auto_strategy(self, sample_endpoint):
        """AUTO strategy should use existing operationId in signature."""
        signature = generate_signature(
            sample_endpoint,
            ultra_compact=False,
            operation_id_strategy=OperationIDStrategy.AUTO
        )

        assert "getUserById" in signature

    def test_signature_with_snake_case_strategy(self, endpoint_without_operation_id):
        """SNAKE_CASE strategy should reflect in signature."""
        signature = generate_signature(
            endpoint_without_operation_id,
            ultra_compact=False,
            operation_id_strategy=OperationIDStrategy.SNAKE_CASE
        )

        assert "api_v1_users" in signature

    def test_signature_with_camel_case_strategy(self, endpoint_without_operation_id):
        """CAMEL_CASE strategy should reflect in signature."""
        signature = generate_signature(
            endpoint_without_operation_id,
            ultra_compact=False,
            operation_id_strategy=OperationIDStrategy.CAMEL_CASE
        )

        # Should be camelCase with method prefix
        assert "get" in signature.lower()
        assert "Api" in signature or "V1" in signature or "Users" in signature

    def test_signature_with_kebab_case_strategy(self, endpoint_without_operation_id):
        """KEBAB_CASE strategy should use hyphens in signature."""
        signature = generate_signature(
            endpoint_without_operation_id,
            ultra_compact=False,
            operation_id_strategy=OperationIDStrategy.KEBAB_CASE
        )

        assert "api-v1-users" in signature

