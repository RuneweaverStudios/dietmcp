"""GraphQL introspection client for schema discovery.

This module provides native GraphQL introspection capabilities, enabling
automatic extraction of queries, mutations, and types from GraphQL APIs.
Differentiates dietmcp from tools like mcp2cli that rely on manual
OpenAPI wrappers.
"""

import httpx
from typing import Any

from dietmcp.models.graphql import (
    GraphQLSchema,
    GraphQLType,
    GraphQLField,
    GraphQLArgument,
    GraphQLOperation,
)
from dietmcp.security.url_validator import validate_url


# Standard GraphQL introspection query
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      name
      kind
      description
      fields {
        name
        description
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
        args {
          name
          description
          type {
            name
            kind
            ofType {
              name
              kind
            }
          }
          defaultValue
        }
        isDeprecated
        deprecationReason
      }
    }
  }
}
"""


class GraphQLIntrospector:
    """Introspect GraphQL APIs to extract schema information."""

    def __init__(self, timeout: float = 30.0) -> None:
        """Initialize introspector with HTTP client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def introspect(
        self, url: str, headers: dict[str, str] | None = None
    ) -> GraphQLSchema:
        """Execute introspection query and parse schema.

        Args:
            url: GraphQL endpoint URL
            headers: Optional HTTP headers (e.g., authentication)

        Returns:
            GraphQLSchema with complete schema information

        Raises:
            httpx.HTTPError: On network or HTTP errors
            ValueError: On invalid GraphQL response or URL validation failure
        """
        # Validate URL is not internal/private (SSRF protection)
        try:
            validate_url(url)
        except ValueError as e:
            raise ValueError(f"URL validation failed: {e}") from e

        headers = headers or {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json={"query": INTROSPECTION_QUERY},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Validate response structure
            if "errors" in data:
                raise ValueError(f"GraphQL errors: {data['errors']}")
            if "data" not in data:
                raise ValueError("Invalid GraphQL response: missing 'data' field")

            return self._parse_schema(data["data"]["__schema"])

    def _parse_schema(self, schema_data: dict[str, Any]) -> GraphQLSchema:
        """Parse introspection schema data into models.

        Args:
            schema_data: Raw introspection schema data

        Returns:
            Parsed GraphQLSchema
        """
        # Extract root type names
        query_type_name = (
            schema_data.get("queryType", {}).get("name") if schema_data else None
        )
        mutation_type_name = (
            schema_data.get("mutationType", {}).get("name") if schema_data else None
        )

        # Parse all types
        types: dict[str, GraphQLType] = {}
        for type_data in schema_data.get("types", []):
            graphql_type = self._parse_type(type_data)
            types[graphql_type.name] = graphql_type

        # Extract queries and mutations
        queries = self._extract_operations(query_type_name, types)
        mutations = self._extract_operations(mutation_type_name, types)

        return GraphQLSchema(
            query_type_name=query_type_name,
            mutation_type_name=mutation_type_name,
            types=types,
            queries=queries,
            mutations=mutations,
        )

    def _parse_type(self, type_data: dict[str, Any]) -> GraphQLType:
        """Parse a single GraphQL type.

        Args:
            type_data: Raw type data from introspection

        Returns:
            GraphQLType instance
        """
        fields: dict[str, GraphQLField] = {}
        for field_data in type_data.get("fields", []):
            field = self._parse_field(field_data)
            fields[field.name] = field

        return GraphQLType(
            name=type_data["name"],
            kind=type_data["kind"],
            description=type_data.get("description"),
            fields=fields if fields else None,
        )

    def _parse_field(self, field_data: dict[str, Any]) -> GraphQLField:
        """Parse a single GraphQL field.

        Args:
            field_data: Raw field data from introspection

        Returns:
            GraphQLField instance
        """
        args = [self._parse_arg(arg_data) for arg_data in field_data.get("args", [])]

        type_info = self._extract_type_info(field_data["type"])

        return GraphQLField(
            name=field_data["name"],
            description=field_data.get("description"),
            type_name=type_info["name"],
            type_kind=type_info["kind"],
            args=args,
            is_deprecated=field_data.get("isDeprecated", False),
            deprecation_reason=field_data.get("deprecationReason"),
        )

    def _parse_arg(self, arg_data: dict[str, Any]) -> GraphQLArgument:
        """Parse a single GraphQL argument.

        Args:
            arg_data: Raw argument data from introspection

        Returns:
            GraphQLArgument instance
        """
        type_info = self._extract_type_info(arg_data["type"])

        return GraphQLArgument(
            name=arg_data["name"],
            type_name=type_info["name"],
            type_kind=type_info["kind"],
            default_value=arg_data.get("defaultValue"),
            description=arg_data.get("description"),
        )

    def _extract_type_info(self, type_data: dict[str, Any]) -> dict[str, str]:
        """Extract type name and kind from nested type structure.

        GraphQL uses wrapping types (NON_NULL, LIST) so we need to
        unwrap to get the actual type name.

        Args:
            type_data: Nested type data

        Returns:
            Dict with 'name' and 'kind' of the actual type
        """
        # Traverse through ofType to get the actual type
        current = type_data
        while current.get("ofType"):
            current = current["ofType"]

        return {
            "name": current.get("name") or "Unknown",
            "kind": current.get("kind") or "UNKNOWN",
        }

    def _extract_operations(
        self, root_type_name: str | None, types: dict[str, GraphQLType]
    ) -> list[GraphQLOperation]:
        """Extract all operations from a root type.

        Args:
            root_type_name: Name of root type (Query or Mutation)
            types: Dictionary of all types

        Returns:
            List of GraphQLOperation instances
        """
        if not root_type_name or root_type_name not in types:
            return []

        root_type = types[root_type_name]
        if not root_type.fields:
            return []

        operations = []
        for field_name, field in root_type.fields.items():
            operation = GraphQLOperation(
                name=field_name,
                description=field.description,
                field=field,
            )
            operations.append(operation)

        return operations

    def extract_queries(self, schema: GraphQLSchema) -> list[GraphQLOperation]:
        """Extract all queries from schema.

        Args:
            schema: Parsed GraphQL schema

        Returns:
            List of query operations
        """
        return schema.queries

    def extract_mutations(self, schema: GraphQLSchema) -> list[GraphQLOperation]:
        """Extract all mutations from schema.

        Args:
            schema: Parsed GraphQL schema

        Returns:
            List of mutation operations
        """
        return schema.mutations
