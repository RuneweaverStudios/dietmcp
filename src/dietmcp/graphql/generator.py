"""GraphQL query generator for dynamic query building from schema.

This module provides dynamic query generation from introspected schemas,
enabling automatic creation of queries/mutations with sensible field selection.
This is a key differentiator from tools like mcp2cli that require manual
query specification.
"""

from typing import Any

from dietmcp.models.graphql import (
    GraphQLSchema,
    GraphQLOperation,
    GraphQLType,
    GraphQLField,
)
from dietmcp.models.tool import ToolDefinition


# Common scalar field names to prefer in auto-selection
_COMMON_SCALAR_FIELDS = [
    "id",
    "name",
    "email",
    "login",
    "title",
    "description",
    "url",
    "createdAt",
    "updatedAt",
    "status",
    "state",
    "type",
]

# GraphQL primitive types that don't need nested selection
_PRIMITIVE_TYPES = {
    "ID",
    "String",
    "Int",
    "Float",
    "Boolean",
    " scalar",
    "SCALAR",
}


class GraphQLQueryGenerator:
    """Generate GraphQL queries and tool definitions from schema.

    This class provides dynamic query generation capabilities:
    - Auto-generate selection sets with sensible defaults
    - Convert operations to MCP tool definitions
    - Build executable query strings with variables
    """

    def __init__(self, schema: GraphQLSchema) -> None:
        """Initialize generator with introspected schema.

        Args:
            schema: GraphQL schema from introspection
        """
        self.schema = schema

    def generate_tools(
        self, ultra_compact: bool = False
    ) -> list[ToolDefinition]:
        """Convert GraphQL operations to MCP tool definitions.

        Args:
            ultra_compact: If True, use ultra-compact signature format

        Returns:
            List of ToolDefinition instances for all queries and mutations
        """
        tools = []

        # Generate tools for queries
        for query in self.schema.queries:
            tool = self._operation_to_tool(query, ultra_compact=ultra_compact)
            tools.append(tool)

        # Generate tools for mutations
        for mutation in self.schema.mutations:
            tool = self._operation_to_tool(mutation, ultra_compact=ultra_compact)
            tools.append(tool)

        return tools

    def _operation_to_tool(
        self, operation: GraphQLOperation, ultra_compact: bool = False
    ) -> ToolDefinition:
        """Convert a GraphQL operation to a ToolDefinition.

        Args:
            operation: GraphQL operation (query or mutation)
            ultra_compact: If True, use ultra-compact signature format

        Returns:
            ToolDefinition instance
        """
        # Build JSON Schema for input parameters
        properties = {}
        required = []

        for arg in operation.field.args:
            arg_type = self._graphql_type_to_json_schema(arg.type_name, arg.type_kind)
            properties[arg.name] = arg_type

            # Mark as required if no default value
            if arg.default_value is None:
                required.append(arg.name)

        input_schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            input_schema["required"] = required

        # Generate description
        description = operation.description or f"GraphQL {operation.name} operation"

        # Add return type info to description
        return_type = operation.field.type_name
        description += f"\n\nReturns: {return_type}"

        return ToolDefinition(
            name=operation.name,
            description=description,
            input_schema=input_schema,
            server_name="graphql",
        )

    def generate_query(
        self, operation: GraphQLOperation, variables: dict[str, Any]
    ) -> str:
        """Generate GraphQL query string with variables.

        Args:
            operation: GraphQL operation to generate query for
            variables: Variable values for the operation

        Returns:
            Executable GraphQL query string

        Example:
            >>> generator.generate_query(user_op, {"login": "octocat"})
            'query GetUser($login: String!) {\\n  user(login: $login) {\\n    login\\n    name\\n  }\\n}'
        """
        operation_type = "mutation" if operation in self.schema.mutations else "query"
        operation_name = f"{operation.name}_{operation_type.title()}"

        # Build variable definitions and arguments
        var_definitions = []
        var_arguments = []

        for arg in operation.field.args:
            var_name = arg.name
            graphql_type = self._graphql_type_string(arg.type_name, arg.type_kind)

            # Add variable definition
            var_definitions.append(f"${var_name}: {graphql_type}")

            # Add argument to operation call
            var_arguments.append(f"{var_name}: ${var_name}")

        # Auto-generate selection set
        selection_set = self.auto_select_fields(operation.field.type_name)

        # Build query string
        query_parts = []
        query_parts.append(f"{operation_type} {operation_name}")

        if var_definitions:
            query_parts.append(f"({', '.join(var_definitions)})")

        query_parts.append("{")

        # Build operation call
        operation_call = f"  {operation.name}"
        if var_arguments:
            operation_call += f"({', '.join(var_arguments)})"
        operation_call += f" {{\n{selection_set}\n  }}"

        query_parts.append(operation_call)
        query_parts.append("}")

        return "\n".join(query_parts)

    def auto_select_fields(self, type_name: str, max_depth: int = 2) -> str:
        """Auto-generate selection set with sensible defaults.

        This method intelligently selects fields based on common patterns:
        - Prefers scalar fields (id, name, email, etc.)
        - Limits nesting depth to avoid over-fetching
        - Skips connection edges without explicit fields
        - Includes __typename for polymorphic types

        Args:
            type_name: Type name to generate selection for
            max_depth: Maximum nesting depth (default: 2)

        Returns:
            Selection set as indented GraphQL string

        Example:
            >>> generator.auto_select_fields("User")
            '    login\\n    name\\n    email'
        """
        if type_name not in self.schema.types:
            # Unknown type - return empty selection
            return ""

        graphql_type = self.schema.types[type_name]

        # Skip if no fields (primitive type)
        if not graphql_type.fields:
            return ""

        # Select fields based on heuristics
        selected_fields = self._select_fields_by_priority(
            graphql_type, current_depth=1, max_depth=max_depth
        )

        return "\n    ".join(selected_fields)

    def _select_fields_by_priority(
        self, graphql_type: GraphQLType, current_depth: int, max_depth: int
    ) -> list[str]:
        """Select fields from type based on priority heuristics.

        Args:
            graphql_type: Type to select fields from
            current_depth: Current nesting depth
            max_depth: Maximum allowed depth

        Returns:
            List of selected field names with nested selections
        """
        if not graphql_type.fields:
            return []

        fields = graphql_type.fields
        selected = []

        # Priority 1: Common scalar fields
        for field_name in _COMMON_SCALAR_FIELDS:
            if field_name in fields:
                field = fields[field_name]
                if self._is_scalar_type(field.type_name):
                    selected.append(field_name)

        # Priority 2: Add __typename for object types (polymorphic)
        if graphql_type.kind == "OBJECT":
            selected.append("__typename")

        # Priority 3: Other scalar fields
        for field_name, field in fields.items():
            if field_name not in selected and self._is_scalar_type(field.type_name):
                selected.append(field_name)

        # Priority 4: Nested object fields (if depth allows)
        if current_depth < max_depth:
            for field_name, field in fields.items():
                if field_name in selected:
                    continue

                # Skip connection edges without explicit field selection
                if field_name in ["edges", "nodes"]:
                    continue

                # Recursively select nested fields
                if field.type_name in self.schema.types:
                    nested_type = self.schema.types[field.type_name]
                    if nested_type.fields:  # It's an object type
                        nested_fields = self._select_fields_by_priority(
                            nested_type, current_depth + 1, max_depth
                        )
                        if nested_fields:
                            nested_selection = "\n    ".join(nested_fields)
                            selected.append(f"{field_name} {{\n    {nested_selection}\n  }}")

        return selected

    def _is_scalar_type(self, type_name: str) -> bool:
        """Check if type is a scalar (primitive) type.

        Args:
            type_name: Type name to check

        Returns:
            True if type is scalar, False if it's a complex object type
        """
        # Check built-in scalars
        if type_name in _PRIMITIVE_TYPES:
            return True

        # Check if type exists in schema but has no fields (custom scalar)
        if type_name in self.schema.types:
            schema_type = self.schema.types[type_name]
            return not schema_type.fields

        # Unknown type - assume scalar
        return True

    def _graphql_type_to_json_schema(
        self, type_name: str, type_kind: str
    ) -> dict[str, Any]:
        """Convert GraphQL type to JSON Schema format.

        Args:
            type_name: GraphQL type name
            type_kind: GraphQL type kind

        Returns:
            JSON Schema type definition
        """
        # Map GraphQL types to JSON Schema types
        type_map = {
            "Int": {"type": "integer"},
            "Float": {"type": "number"},
            "String": {"type": "string"},
            "Boolean": {"type": "boolean"},
            "ID": {"type": "string"},
        }

        # Handle NON_NULL wrapper
        is_required = type_kind == "NON_NULL"

        # Get base type (unwrap NON_NULL and LIST)
        base_type_name = type_name
        if base_type_name.endswith("!"):
            base_type_name = base_type_name[:-1]

        # Check if it's a known scalar type
        if base_type_name in type_map:
            schema = type_map[base_type_name].copy()
        else:
            # Unknown/custom type - use string or object
            if base_type_name in self.schema.types:
                schema_type = self.schema.types[base_type_name]
                if schema_type.fields:
                    # It's an object type
                    schema = {"type": "object"}
                else:
                    # It's a custom scalar
                    schema = {"type": "string"}
            else:
                # Default to string
                schema = {"type": "string"}

        # Handle LIST types
        if type_kind == "LIST" or "[" in type_name:
            return {
                "type": "array",
                "items": schema,
            }

        return schema

    def _graphql_type_string(self, type_name: str, type_kind: str) -> str:
        """Generate GraphQL type string for variable definitions.

        Args:
            type_name: GraphQL type name
            type_kind: GraphQL type kind

        Returns:
            GraphQL type string (e.g., "String!", "[String]")
        """
        # Handle NON_NULL
        if type_kind == "NON_NULL":
            return f"{type_name}!"

        # Handle LIST
        if type_kind == "LIST":
            return f"[{type_name}]"

        return type_name
