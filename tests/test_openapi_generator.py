"""Tests for OpenAPI tool generator."""

import pytest
from dietmcp.openapi.generator import OpenAPIToolGenerator, generate_signature
from dietmcp.models.openapi import OpenAPISpec, OpenAPIEndpoint, OpenAPIParameter


class TestOpenAPIToolGenerator:
    """Test OpenAPI to ToolDefinition conversion."""

    def test_generate_simple_get_tool(self):
        """Test generating a tool from a simple GET endpoint."""
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="GET",
            operation_id="getUser",
            summary="Get user by ID",
            parameters=[
                OpenAPIParameter(
                    name="id",
                    in_="path",
                    required=True,
                    schema_={"type": "string"},
                ),
                OpenAPIParameter(
                    name="verbose",
                    in_="query",
                    required=False,
                    schema_={"type": "boolean"},
                ),
            ],
        )

        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint, "testapi", ultra_compact=False)

        assert tool is not None
        assert tool.name == "getUser"
        assert tool.description == "Get user by ID"
        assert tool.server_name == "testapi"
        assert "id" in tool.input_schema["properties"]
        assert "verbose" in tool.input_schema["properties"]
        assert "id" in tool.input_schema["required"]
        assert "verbose" not in tool.input_schema["required"]

    def test_generate_post_tool_with_body(self):
        """Test generating a tool from a POST endpoint with request body."""
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="POST",
            operation_id="createUser",
            description="Create a new user",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                            },
                            "required": ["name", "email"],
                        }
                    }
                }
            },
        )

        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint, "testapi", ultra_compact=False)

        assert tool is not None
        assert tool.name == "createUser"
        assert "request_body" in tool.input_schema["properties"]
        assert "request_body" in tool.input_schema["required"]
        assert tool.input_schema["properties"]["request_body"]["type"] == "object"

    def test_generate_operation_id(self):
        """Test automatic operation ID generation."""
        generator = OpenAPIToolGenerator()

        # GET /users
        endpoint1 = OpenAPIEndpoint(path="/users", method="GET")
        assert generator._generate_operation_id(endpoint1) == "getUsers"

        # POST /users/{id}/posts
        endpoint2 = OpenAPIEndpoint(path="/users/{id}/posts", method="POST")
        assert generator._generate_operation_id(endpoint2) == "postUsersPosts"

        # GET /api/v1/users
        endpoint3 = OpenAPIEndpoint(path="/api/v1/users", method="GET")
        assert generator._generate_operation_id(endpoint3) == "getApiV1Users"

    def test_compact_signature(self):
        """Test ultra-compact signature generation."""
        endpoint = OpenAPIEndpoint(
            path="/users/{id}",
            method="GET",
            operation_id="getUser",
            summary="Get user by ID",
            parameters=[
                OpenAPIParameter(
                    name="id",
                    in_="path",
                    required=True,
                    schema_={"type": "string"},
                ),
                OpenAPIParameter(
                    name="limit",
                    in_="query",
                    required=False,
                    schema_={"type": "integer"},
                ),
                OpenAPIParameter(
                    name="sort",
                    in_="query",
                    required=False,
                    schema_={"type": "string", "enum": ["asc", "desc"]},
                ),
            ],
        )

        # Ultra-compact signature
        sig = generate_signature(endpoint, ultra_compact=True)
        assert "getUser(id, limit?" in sig
        # Enum should show values
        assert "asc" in sig or "desc" in sig

        # Standard signature
        sig_std = generate_signature(endpoint, ultra_compact=False)
        assert "getUser(id: str, ?limit: int" in sig_std

    def test_generate_multiple_tools(self):
        """Test generating tools from a full spec."""
        spec = OpenAPISpec(
            title="Test API",
            version="1.0.0",
            endpoints=[
                OpenAPIEndpoint(
                    path="/users",
                    method="GET",
                    operation_id="getUsers",
                    summary="List all users",
                ),
                OpenAPIEndpoint(
                    path="/users/{id}",
                    method="GET",
                    operation_id="getUser",
                    summary="Get user by ID",
                    parameters=[
                        OpenAPIParameter(
                            name="id",
                            in_="path",
                            required=True,
                            schema_={"type": "string"},
                        )
                    ],
                ),
                OpenAPIEndpoint(
                    path="/users",
                    method="POST",
                    operation_id="createUser",
                    summary="Create a user",
                    request_body={
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    },
                ),
            ],
        )

        generator = OpenAPIToolGenerator()
        tools = generator.generate_tools(spec, server_name="testapi")

        assert len(tools) == 3
        assert {t.name for t in tools} == {"getUsers", "getUser", "createUser"}
        assert all(t.server_name == "testapi" for t in tools)

    def test_array_parameter_type(self):
        """Test handling of array parameters."""
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="GET",
            operation_id="getUsers",
            parameters=[
                OpenAPIParameter(
                    name="tags",
                    in_="query",
                    required=False,
                    schema_={"type": "array", "items": {"type": "string"}},
                ),
            ],
        )

        # Ultra-compact: [str] shorthand
        sig = generate_signature(endpoint, ultra_compact=True)
        assert "[str]" in sig

        # Standard: list[str]
        sig_std = generate_signature(endpoint, ultra_compact=False)
        assert "list[str]" in sig_std

    def test_object_parameter_type(self):
        """Test handling of object parameters."""
        endpoint = OpenAPIEndpoint(
            path="/users",
            method="POST",
            operation_id="createUser",
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "age": {"type": "integer"},
                                "address": {
                                    "type": "object",
                                    "properties": {
                                        "street": {"type": "string"},
                                        "city": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                }
            },
        )

        generator = OpenAPIToolGenerator()
        tool = generator._generate_tool(endpoint, "testapi", ultra_compact=False)

        # Should have request_body property
        assert "request_body" in tool.input_schema["properties"]
        body_schema = tool.input_schema["properties"]["request_body"]
        assert body_schema["type"] == "object"
        assert "properties" in body_schema
        assert "name" in body_schema["properties"]
