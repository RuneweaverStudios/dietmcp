# Operation ID Generation Strategies

## Overview

OpenAPI tool generation now supports multiple strategies for generating operation IDs from endpoint paths and HTTP methods. This allows flexibility in naming conventions to match different API styles and preferences.

## Available Strategies

### AUTO (default)
Uses the `operationId` from the OpenAPI specification if present, otherwise falls back to CAMEL_CASE generation.

```python
# With operationId in spec: "getUserById"
# Without operationId: "getUsers"
```

### PATH_METHOD
Generates `{path}_{method}` format, preserving original case.

```python
GET /api/v1/users/{id} -> "api_v1_users_get"
POST /users/{id}/posts -> "users_id_posts_post"
```

### PATH_LOWER
Generates lowercase path with underscores, no method suffix. Removes path parameters.

```python
GET /api/v1/users/{id} -> "api_v1_users"
POST /users/{id}/posts -> "users_posts"
```

### CAMEL_CASE
Generates camelCase with method prefix and capitalized path segments. Removes path parameters.

```python
GET /users -> "getUsers"
POST /api/v1/users/{id}/posts -> "postApiV1UsersPosts"
GET /users/{id} -> "getUsers"
```

### SNAKE_CASE
Generates lowercase with underscores, preserving parameter names. No method suffix.

```python
GET /users/{id} -> "users_id"
POST /api/v1/users/{userId}/posts/{postId} -> "api_v1_users_userid_posts_postid"
```

### KEBAB_CASE
Generates lowercase with hyphens. Removes path parameters.

```python
GET /api/v1/users/{id} -> "api-v1-users"
POST /users/{id}/posts -> "users-posts"
```

## Usage

### In Code

```python
from dietmcp.openapi import (
    OpenAPIToolGenerator,
    OperationIDStrategy,
    generate_operation_id
)
from dietmcp.models.openapi import OpenAPIEndpoint

# Using the standalone function
endpoint = OpenAPIEndpoint(
    path="/users/{id}",
    method="GET",
    operation_id=None,
    # ... other fields
)

operation_id = generate_operation_id(
    endpoint,
    OperationIDStrategy.SNAKE_CASE
)
# Returns: "users_id"

# Using the generator class
generator = OpenAPIToolGenerator(
    operation_id_strategy=OperationIDStrategy.CAMEL_CASE
)
tools = generator.generate_tools(spec, server_name="my-api")
```

### In Signatures

```python
from dietmcp.openapi import generate_signature, OperationIDStrategy

signature = generate_signature(
    endpoint,
    ultra_compact=True,
    operation_id_strategy=OperationIDStrategy.KEBAB_CASE
)
```

## Implementation Details

- **Path Parameter Handling**: Most strategies remove path parameters (e.g., `{id}`), except SNAKE_CASE which preserves them as `_id`
- **Case Sensitivity**: Only PATH_METHOD preserves original case; all others convert to lowercase or camelCase
- **Method Suffix**: AUTO, PATH_METHOD, and CAMEL_CASE include the HTTP method in the generated ID
- **Double Underscore Prevention**: SNAKE_CASE cleans up consecutive underscores to avoid `__` in generated IDs

## Testing

Comprehensive tests cover:
- Each strategy with various path patterns
- Root paths and trailing slashes
- Multiple path parameters
- Nested paths
- Integration with OpenAPIToolGenerator
- Integration with signature generation

Run tests with:
```bash
pytest tests/unit/test_openapi_generator.py::TestOperationIDStrategies -v
```

## Examples

See `examples/operation_id_strategies.py` for a complete demonstration of all strategies with various endpoint patterns.
