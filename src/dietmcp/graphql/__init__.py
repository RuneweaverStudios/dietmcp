"""GraphQL introspection, schema analysis, and execution."""

from dietmcp.graphql.introspection import GraphQLIntrospector, INTROSPECTION_QUERY
from dietmcp.graphql.generator import GraphQLQueryGenerator
from dietmcp.graphql.executor import GraphQLExecutor, GraphQLError

__all__ = [
    "GraphQLIntrospector",
    "INTROSPECTION_QUERY",
    "GraphQLQueryGenerator",
    "GraphQLExecutor",
    "GraphQLError",
]
