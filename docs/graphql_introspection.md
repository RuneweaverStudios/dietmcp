# GraphQL Introspection Client

## Overview

Native GraphQL introspection client for dietmcp that enables automatic extraction of queries, mutations, and types from GraphQL APIs. This differentiates dietmcp from tools like mcp2cli that rely on manual OpenAPI wrappers.

## Files Created

### 1. `/Users/ghost/Desktop/dietmcp/src/dietmcp/models/graphql.py`

Immutable dataclass models for GraphQL schema representation:

- **`GraphQLSchema`**: Complete schema with queries, mutations, and types
- **`GraphQLType`**: Type definition (SCALAR, OBJECT, LIST, NON_NULL, etc.)
- **`GraphQLField`**: Field definition with arguments and return type
- **`GraphQLArgument`**: Argument definition with type and default value
- **`GraphQLOperation`**: Query or mutation operation

All models use `@dataclass(frozen=True)` for immutability.

### 2. `/Users/ghost/Desktop/dietmcp/src/dietmcp/graphql/introspection.py`

`GraphQLIntrospector` class with the following capabilities:

- **`introspect(url, headers)`**: Execute introspection query and parse schema
- **`extract_queries(schema)`**: Extract all query operations
- **`extract_mutations(schema)`**: Extract all mutation operations
- **`INTROSPECTION_QUERY`**: Standard GraphQL introspection query constant

### 3. `/Users/ghost/Desktop/dietmcp/src/dietmcp/graphql/__init__.py`

Package exports for GraphQL functionality.

### 4. `/Users/ghost/Desktop/dietmcp/examples/graphql_introspection.py`

Example usage demonstrating introspection of a public GraphQL API.

## Key Features

1. **Native GraphQL Support**: Uses standard GraphQL introspection query
2. **Type-Safe Models**: Frozen dataclasses prevent mutation
3. **Async HTTP Client**: Uses httpx for non-blocking requests
4. **Comprehensive Extraction**: Parses types, fields, arguments, and descriptions
5. **Error Handling**: Validates GraphQL responses and reports errors

## Usage Example

```python
from dietmcp.graphql import GraphQLIntrospector

async def introspect_api(url: str):
    introspector = GraphQLIntrospector(timeout=30.0)
    schema = await introspector.introspect(url)

    print(f"Total types: {schema.total_types}")
    print(f"Queries: {len(schema.queries)}")
    print(f"Mutations: {len(schema.mutations)}")

    for query in schema.queries:
        print(f"{query.name}: {query.field.type_name}")
```

## Dependencies

Added to `pyproject.toml`:
- `httpx>=0.27.0` - Async HTTP client for GraphQL requests

## Next Steps

- Add unit tests for introspection parsing
- Integrate with skill summary generation
- Add CLI command for introspection
- Support for custom introspection queries
- Caching for repeated introspection calls
