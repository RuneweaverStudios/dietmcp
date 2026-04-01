"""GraphQL schema models for introspection results.

All models are frozen (immutable) to prevent hidden side effects.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphQLType:
    """Represents a GraphQL type definition.

    Attributes:
        name: Type name (e.g., "User", "String")
        kind: Type kind (SCALAR, OBJECT, LIST, NON_NULL, etc.)
        description: Optional type description
        fields: Dictionary of field names to GraphQLField definitions
    """

    name: str
    kind: str
    description: str | None = None
    fields: dict[str, "GraphQLField"] | None = None


@dataclass(frozen=True)
class GraphQLField:
    """Represents a GraphQL field definition.

    Attributes:
        name: Field name
        description: Optional field description
        type_name: Return type name (e.g., "User", "String")
        type_kind: Return type kind (SCALAR, OBJECT, LIST, NON_NULL, etc.)
        args: List of argument definitions
        is_deprecated: Whether the field is deprecated
        deprecation_reason: Reason for deprecation if applicable
    """

    name: str
    description: str | None
    type_name: str
    type_kind: str
    args: list["GraphQLArgument"]
    is_deprecated: bool = False
    deprecation_reason: str | None = None


@dataclass(frozen=True)
class GraphQLArgument:
    """Represents a GraphQL argument definition.

    Attributes:
        name: Argument name
        type_name: Argument type name
        type_kind: Argument type kind
        default_value: Default value if provided
        description: Optional argument description
    """

    name: str
    type_name: str
    type_kind: str
    default_value: Any | None = None
    description: str | None = None


@dataclass(frozen=True)
class GraphQLOperation:
    """Represents a GraphQL operation (query or mutation).

    Attributes:
        name: Operation name
        description: Optional operation description
        field: Field definition with args and return type
    """

    name: str
    description: str | None
    field: GraphQLField


@dataclass(frozen=True)
class GraphQLSchema:
    """Complete GraphQL schema from introspection.

    Attributes:
        query_type_name: Name of the Query root type
        mutation_type_name: Name of the Mutation root type (optional)
        types: Dictionary of all type definitions
        queries: List of all query operations
        mutations: List of all mutation operations
    """

    query_type_name: str | None
    mutation_type_name: str | None
    types: dict[str, GraphQLType]
    queries: list[GraphQLOperation]
    mutations: list[GraphQLOperation]

    @property
    def has_queries(self) -> bool:
        """Check if schema has any queries."""
        return len(self.queries) > 0

    @property
    def has_mutations(self) -> bool:
        """Check if schema has any mutations."""
        return len(self.mutations) > 0

    @property
    def total_types(self) -> int:
        """Get total number of types in schema."""
        return len(self.types)
