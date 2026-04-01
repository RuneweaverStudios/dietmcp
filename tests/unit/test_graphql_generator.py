"""Tests for GraphQL query generation functionality."""

from __future__ import annotations

import pytest

from dietmcp.graphql.generator import GraphQLQueryGenerator
from dietmcp.models.graphql import (
    GraphQLSchema,
    GraphQLType,
    GraphQLField,
    GraphQLArgument,
    GraphQLOperation,
)
from dietmcp.models.tool import ToolDefinition


@pytest.fixture
def sample_schema():
    """Create a sample GraphQL schema for testing."""
    types = {
        "Query": GraphQLType(
            name="Query",
            kind="OBJECT",
            description=None,
            fields={
                "user": GraphQLField(
                    name="user",
                    description="Get a user by login",
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
                "repository": GraphQLField(
                    name="repository",
                    description="Get a repository",
                    type_name="Repository",
                    type_kind="OBJECT",
                    args=[
                        GraphQLArgument(
                            name="owner",
                            type_name="String",
                            type_kind="SCALAR",
                            default_value=None,
                            description="Repository owner",
                        ),
                        GraphQLArgument(
                            name="name",
                            type_name="String",
                            type_kind="SCALAR",
                            default_value=None,
                            description="Repository name",
                        ),
                    ],
                ),
                "search": GraphQLField(
                    name="search",
                    description="Search repositories",
                    type_name="SearchResult",
                    type_kind="OBJECT",
                    args=[
                        GraphQLArgument(
                            name="query",
                            type_name="String",
                            type_kind="SCALAR",
                            default_value=None,
                            description="Search query",
                        ),
                        GraphQLArgument(
                            name="limit",
                            type_name="Int",
                            type_kind="SCALAR",
                            default_value="10",
                            description="Max results",
                        ),
                    ],
                ),
            },
        ),
        "Mutation": GraphQLType(
            name="Mutation",
            kind="OBJECT",
            description=None,
            fields={
                "addComment": GraphQLField(
                    name="addComment",
                    description="Add a comment to an issue",
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
            },
        ),
        "User": GraphQLType(
            name="User",
            kind="OBJECT",
            description="A user",
            fields={
                "login": GraphQLField(
                    name="login",
                    description="Username",
                    type_name="String",
                    type_kind="SCALAR",
                    args=[],
                ),
                "name": GraphQLField(
                    name="name",
                    description="Full name",
                    type_name="String",
                    type_kind="SCALAR",
                    args=[],
                ),
                "email": GraphQLField(
                    name="email",
                    description="Email",
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
                "repositories": GraphQLField(
                    name="repositories",
                    description="User repositories",
                    type_name="RepositoryConnection",
                    type_kind="OBJECT",
                    args=[],
                ),
            },
        ),
        "Repository": GraphQLType(
            name="Repository",
            kind="OBJECT",
            description="A repository",
            fields={
                "name": GraphQLField(
                    name="name",
                    description="Repository name",
                    type_name="String",
                    type_kind="SCALAR",
                    args=[],
                ),
                "description": GraphQLField(
                    name="description",
                    description="Repository description",
                    type_name="String",
                    type_kind="SCALAR",
                    args=[],
                ),
                "url": GraphQLField(
                    name="url",
                    description="Repository URL",
                    type_name="String",
                    type_kind="SCALAR",
                    args=[],
                ),
                "owner": GraphQLField(
                    name="owner",
                    description="Repository owner",
                    type_name="User",
                    type_kind="OBJECT",
                    args=[],
                ),
            },
        ),
        "Comment": GraphQLType(
            name="Comment",
            kind="OBJECT",
            description="A comment",
            fields={
                "id": GraphQLField(
                    name="id",
                    description="Comment ID",
                    type_name="ID",
                    type_kind="SCALAR",
                    args=[],
                ),
                "body": GraphQLField(
                    name="body",
                    description="Comment body",
                    type_name="String",
                    type_kind="SCALAR",
                    args=[],
                ),
            },
        ),
        "SearchResult": GraphQLType(
            name="SearchResult",
            kind="OBJECT",
            description="Search results",
            fields={
                "count": GraphQLField(
                    name="count",
                    description="Result count",
                    type_name="Int",
                    type_kind="SCALAR",
                    args=[],
                ),
                "items": GraphQLField(
                    name="items",
                    description="Result items",
                    type_name="Repository",
                    type_kind="OBJECT",
                    args=[],
                ),
            },
        ),
        "RepositoryConnection": GraphQLType(
            name="RepositoryConnection",
            kind="OBJECT",
            description="Repository connection",
            fields={
                "totalCount": GraphQLField(
                    name="totalCount",
                    description="Total count",
                    type_name="Int",
                    type_kind="SCALAR",
                    args=[],
                ),
                "edges": GraphQLField(
                    name="edges",
                    description="Connection edges",
                    type_name="RepositoryEdge",
                    type_kind="OBJECT",
                    args=[],
                ),
            },
        ),
        "RepositoryEdge": GraphQLType(
            name="RepositoryEdge",
            kind="OBJECT",
            description="Repository edge",
            fields={
                "node": GraphQLField(
                    name="node",
                    description="Repository node",
                    type_name="Repository",
                    type_kind="OBJECT",
                    args=[],
                ),
            },
        ),
        "String": GraphQLType(
            name="String",
            kind="SCALAR",
            description="String scalar",
            fields=None,
        ),
        "ID": GraphQLType(
            name="ID",
            kind="SCALAR",
            description="ID scalar",
            fields=None,
        ),
        "Int": GraphQLType(
            name="Int",
            kind="SCALAR",
            description="Int scalar",
            fields=None,
        ),
        "Boolean": GraphQLType(
            name="Boolean",
            kind="SCALAR",
            description="Boolean scalar",
            fields=None,
        ),
    }

    queries = [
        GraphQLOperation(
            name="user",
            description="Get a user by login",
            field=types["Query"].fields["user"],
        ),
        GraphQLOperation(
            name="repository",
            description="Get a repository",
            field=types["Query"].fields["repository"],
        ),
        GraphQLOperation(
            name="search",
            description="Search repositories",
            field=types["Query"].fields["search"],
        ),
    ]

    mutations = [
        GraphQLOperation(
            name="addComment",
            description="Add a comment to an issue",
            field=types["Mutation"].fields["addComment"],
        ),
    ]

    return GraphQLSchema(
        query_type_name="Query",
        mutation_type_name="Mutation",
        types=types,
        queries=queries,
        mutations=mutations,
    )


@pytest.fixture
def generator(sample_schema):
    """Create GraphQLQueryGenerator instance with sample schema."""
    return GraphQLQueryGenerator(sample_schema)


class TestGraphQLQueryGenerator:
    """Test suite for GraphQLQueryGenerator."""

    def test_init(self, sample_schema):
        """Test generator initialization."""
        generator = GraphQLQueryGenerator(sample_schema)
        assert generator.schema == sample_schema

    def test_generate_tools(self, generator):
        """Test generating tools from schema."""
        tools = generator.generate_tools()

        assert len(tools) == 4  # 3 queries + 1 mutation
        assert all(isinstance(tool, ToolDefinition) for tool in tools)

    def test_generate_tools_query(self, generator):
        """Test generating tool from query operation."""
        tools = generator.generate_tools()
        query_tools = [t for t in tools if t.name == "user"]

        assert len(query_tools) == 1
        tool = query_tools[0]

        assert tool.name == "user"
        assert "user" in tool.description.lower()
        assert tool.input_schema["type"] == "object"
        assert "login" in tool.input_schema["properties"]

    def test_generate_tools_mutation(self, generator):
        """Test generating tool from mutation operation."""
        tools = generator.generate_tools()
        mutation_tools = [t for t in tools if t.name == "addComment"]

        assert len(mutation_tools) == 1
        tool = mutation_tools[0]

        assert tool.name == "addComment"
        assert "comment" in tool.description.lower()
        assert "subjectId" in tool.input_schema["properties"]
        assert "body" in tool.input_schema["properties"]

    def test_generate_tools_with_required_fields(self, generator):
        """Test that required fields are correctly identified."""
        tools = generator.generate_tools()
        user_tool = next(t for t in tools if t.name == "user")

        assert "required" in user_tool.input_schema
        assert "login" in user_tool.input_schema["required"]

    def test_generate_tools_with_optional_fields(self, generator):
        """Test that optional fields (with defaults) are not required."""
        tools = generator.generate_tools()
        search_tool = next(t for t in tools if t.name == "search")

        assert "required" in search_tool.input_schema
        assert "query" in search_tool.input_schema["required"]
        assert "limit" not in search_tool.input_schema["required"]

    def test_generate_tools_return_type_in_description(self, generator):
        """Test that return type is included in description."""
        tools = generator.generate_tools()
        user_tool = next(t for t in tools if t.name == "user")

        assert "Returns:" in user_tool.description
        assert "User" in user_tool.description

    def test_generate_query(self, generator):
        """Test generating GraphQL query string."""
        user_operation = generator.schema.queries[0]
        query = generator.generate_query(user_operation, {"login": "octocat"})

        assert "query user_Query" in query
        assert "$login: String" in query
        assert "user(login: $login)" in query
        assert "login" in query  # Field selection

    def test_generate_query_multiple_variables(self, generator):
        """Test generating query with multiple variables."""
        repo_operation = generator.schema.queries[1]
        query = generator.generate_query(
            repo_operation,
            {"owner": "octocat", "name": "Hello-World"}
        )

        assert "$owner: String" in query
        assert "$name: String" in query
        assert "repository(owner: $owner, name: $name)" in query

    def test_generate_mutation(self, generator):
        """Test generating GraphQL mutation string."""
        mutation_operation = generator.schema.mutations[0]
        mutation = generator.generate_query(
            mutation_operation,
            {"subjectId": "123", "body": "Great work!"}
        )

        assert "mutation addComment_Mutation" in mutation
        assert "$subjectId: ID" in mutation
        assert "$body: String" in mutation
        assert "addComment(subjectId: $subjectId, body: $body)" in mutation

    def test_auto_select_fields(self, generator):
        """Test auto-selecting fields for a type."""
        selection = generator.auto_select_fields("User")

        # Should include common scalar fields
        assert "login" in selection
        assert "__typename" in selection

    def test_auto_select_fields_with_nesting(self, generator):
        """Test auto-selecting fields with nested objects."""
        selection = generator.auto_select_fields("Repository", max_depth=2)

        # Should include scalar fields
        assert "name" in selection
        assert "url" in selection

    def test_auto_select_fields_unknown_type(self, generator):
        """Test auto-selecting fields for unknown type."""
        selection = generator.auto_select_fields("UnknownType")

        assert selection == ""

    def test_auto_select_fields_scalar_type(self, generator):
        """Test auto-selecting fields for scalar type."""
        selection = generator.auto_select_fields("String")

        assert selection == ""

    def test_is_scalar_type_primitive(self, generator):
        """Test scalar type detection for primitives."""
        assert generator._is_scalar_type("String") is True
        assert generator._is_scalar_type("Int") is True
        assert generator._is_scalar_type("Float") is True
        assert generator._is_scalar_type("Boolean") is True
        assert generator._is_scalar_type("ID") is True

    def test_is_scalar_type_custom_scalar(self, generator):
        """Test scalar type detection for custom scalars."""
        # Custom scalar with no fields
        assert generator._is_scalar_type("DateTime") is True  # Unknown type

    def test_is_scalar_type_object(self, generator):
        """Test scalar type detection for object types."""
        assert generator._is_scalar_type("User") is False
        assert generator._is_scalar_type("Repository") is False

    def test_graphql_type_to_json_schema_string(self, generator):
        """Test converting GraphQL String to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("String", "SCALAR")

        assert schema["type"] == "string"

    def test_graphql_type_to_json_schema_int(self, generator):
        """Test converting GraphQL Int to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("Int", "SCALAR")

        assert schema["type"] == "integer"

    def test_graphql_type_to_json_schema_float(self, generator):
        """Test converting GraphQL Float to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("Float", "SCALAR")

        assert schema["type"] == "number"

    def test_graphql_type_to_json_schema_boolean(self, generator):
        """Test converting GraphQL Boolean to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("Boolean", "SCALAR")

        assert schema["type"] == "boolean"

    def test_graphql_type_to_json_schema_id(self, generator):
        """Test converting GraphQL ID to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("ID", "SCALAR")

        assert schema["type"] == "string"

    def test_graphql_type_to_json_schema_object(self, generator):
        """Test converting GraphQL object to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("User", "OBJECT")

        assert schema["type"] == "object"

    def test_graphql_type_to_json_schema_list(self, generator):
        """Test converting GraphQL LIST to JSON Schema."""
        schema = generator._graphql_type_to_json_schema("String", "LIST")

        assert schema["type"] == "array"
        assert "items" in schema
        assert schema["items"]["type"] == "string"

    def test_graphql_type_string_non_null(self, generator):
        """Test generating GraphQL type string for NON_NULL."""
        type_str = generator._graphql_type_string("String", "NON_NULL")

        assert type_str == "String!"

    def test_graphql_type_string_list(self, generator):
        """Test generating GraphQL type string for LIST."""
        type_str = generator._graphql_type_string("String", "LIST")

        assert type_str == "[String]"

    def test_graphql_type_string_scalar(self, generator):
        """Test generating GraphQL type string for scalar."""
        type_str = generator._graphql_type_string("String", "SCALAR")

        assert type_str == "String"


class TestGraphQLQueryGeneratorEdgeCases:
    """Test edge cases and special scenarios."""

    def test_generate_tools_empty_schema(self):
        """Test generating tools from empty schema."""
        schema = GraphQLSchema(
            query_type_name=None,
            mutation_type_name=None,
            types={},
            queries=[],
            mutations=[],
        )

        generator = GraphQLQueryGenerator(schema)
        tools = generator.generate_tools()

        assert len(tools) == 0

    def test_generate_tools_no_queries(self):
        """Test generating tools with no queries."""
        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name="Mutation",
            types={},
            queries=[],
            mutations=[],
        )

        generator = GraphQLQueryGenerator(schema)
        tools = generator.generate_tools()

        assert len(tools) == 0

    def test_generate_tools_no_mutations(self):
        """Test generating tools with no mutations."""
        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name=None,
            types={},
            queries=[
                GraphQLOperation(
                    name="hello",
                    description="Say hello",
                    field=GraphQLField(
                        name="hello",
                        description="Say hello",
                        type_name="String",
                        type_kind="SCALAR",
                        args=[],
                    ),
                )
            ],
            mutations=[],
        )

        generator = GraphQLQueryGenerator(schema)
        tools = generator.generate_tools()

        assert len(tools) == 1
        assert tools[0].name == "hello"

    def test_generate_query_no_args(self):
        """Test generating query with no arguments."""
        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name=None,
            types={
                "Query": GraphQLType(
                    name="Query",
                    kind="OBJECT",
                    description=None,
                    fields={
                        "version": GraphQLField(
                            name="version",
                            description="API version",
                            type_name="String",
                            type_kind="SCALAR",
                            args=[],
                        )
                    },
                ),
                "String": GraphQLType(
                    name="String",
                    kind="SCALAR",
                    description=None,
                    fields=None,
                ),
            },
            queries=[
                GraphQLOperation(
                    name="version",
                    description="API version",
                    field=GraphQLField(
                        name="version",
                        description="API version",
                        type_name="String",
                        type_kind="SCALAR",
                        args=[],
                    ),
                )
            ],
            mutations=[],
        )

        generator = GraphQLQueryGenerator(schema)
        version_operation = schema.queries[0]
        query = generator.generate_query(version_operation, {})

        assert "query version_Query" in query
        # When there are no args, no parentheses are added
        assert "version {" in query

    def test_auto_select_fields_max_depth_limit(self, generator):
        """Test that max_depth limits field selection depth."""
        # With max_depth=1, should not select nested object fields
        selection = generator.auto_select_fields("Repository", max_depth=1)

        # Should have scalar fields but not deeply nested ones
        assert "name" in selection or "description" in selection

    def test_operation_to_tool_no_description(self):
        """Test tool generation when operation has no description."""
        operation = GraphQLOperation(
            name="test",
            description=None,
            field=GraphQLField(
                name="test",
                description=None,
                type_name="String",
                type_kind="SCALAR",
                args=[],
            ),
        )

        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name=None,
            types={},
            queries=[operation],
            mutations=[],
        )

        generator = GraphQLQueryGenerator(schema)
        tool = generator._operation_to_tool(operation, ultra_compact=False)

        # Should have default description
        assert "test operation" in tool.description.lower()

    def test_graphql_type_to_json_schema_unknown_type(self):
        """Test JSON Schema conversion for unknown type."""
        schema = GraphQLSchema(
            query_type_name="Query",
            mutation_type_name=None,
            types={},
            queries=[],
            mutations=[],
        )

        generator = GraphQLQueryGenerator(schema)
        json_schema = generator._graphql_type_to_json_schema("UnknownType", "OBJECT")

        # Should default to string for unknown types
        assert json_schema["type"] == "string"

    def test_auto_select_fields_connection_without_explicit_fields(self, generator):
        """Test that connection edges are skipped without explicit field selection."""
        # Repository has RepositoryConnection type
        selection = generator.auto_select_fields("User", max_depth=1)

        # Should include scalar fields but skip edges without explicit selection
        assert "login" in selection
        # edges should be skipped at max_depth=1
        assert "edges {" not in selection


class TestGraphQLQueryGeneratorComplexScenarios:
    """Test complex real-world scenarios."""

    def test_generate_query_with_nested_selection(self, generator):
        """Test generating query that includes nested object selection."""
        repo_operation = generator.schema.queries[1]
        query = generator.generate_query(
            repo_operation,
            {"owner": "octocat", "name": "Hello-World"}
        )

        # Should contain nested field selection
        assert "query repository_Query" in query
        assert "repository(" in query

    def test_generate_tools_all_argument_types(self, generator):
        """Test tool generation with various argument types."""
        tools = generator.generate_tools()

        # Check that different types are handled
        for tool in tools:
            if tool.name == "user":
                assert tool.input_schema["properties"]["login"]["type"] == "string"
            elif tool.name == "addComment":
                assert tool.input_schema["properties"]["subjectId"]["type"] == "string"
                assert tool.input_schema["properties"]["body"]["type"] == "string"
            elif tool.name == "search":
                # limit has default value, should be optional
                assert "limit" in tool.input_schema["properties"]
                assert "limit" not in tool.input_schema.get("required", [])

    def test_select_fields_priority_order(self, generator):
        """Test that fields are selected by priority (common scalars first)."""
        selection = generator.auto_select_fields("User")

        # Common scalar fields should be present
        assert "login" in selection
        assert "name" in selection or "email" in selection

        # __typename should be present for object types
        assert "__typename" in selection

    def test_generate_query_preserves_variable_order(self, generator):
        """Test that query generation preserves argument order."""
        repo_operation = generator.schema.queries[1]
        query = generator.generate_query(
            repo_operation,
            {"owner": "octocat", "name": "Hello-World"}
        )

        # Variables should be in definition order
        lines = query.split("\n")
        var_line = [l for l in lines if "$" in l and "Repository_Query" not in l][0]

        # owner should come before name
        owner_pos = var_line.find("$owner")
        name_pos = var_line.find("$name")
        assert owner_pos < name_pos
