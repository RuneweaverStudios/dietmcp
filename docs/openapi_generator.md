# OpenAPI Tool Generator

## Overview

The OpenAPI Tool Generator converts OpenAPI 3.0.x specifications into unified `ToolDefinition` objects, enabling HTTP APIs to be exposed as dietmcp skills with the same compact formatting and caching as native MCP servers.

## Features

- **Automatic Operation ID Generation**: Generates operation IDs from HTTP method + path (e.g., `GET /users/{id}` → `getUsersById`)
- **Parameter Mapping**: Converts OpenAPI parameters to JSON Schema input_schema
- **Request Body Handling**: Merges request bodies into input_schema as `request_body` parameter
- **Ultra-Compact Signatures**: Generates 13-15 token signatures per tool (52% reduction vs standard)
- **Unified Integration**: Works seamlessly with existing `skills_generator` for consistent output

## Usage

### Basic Example

```python
from dietmcp.openapi.parser import OpenAPIParser
from dietmcp.openapi.generator import OpenAPIToolGenerator

# Parse OpenAPI spec
parser = OpenAPIParser()
spec = parser.parse_spec("https://petstore.swagger.io/v2/swagger.json")

# Generate tools
generator = OpenAPIToolGenerator()
tools = generator.generate_tools(
    spec,
    server_name="petstore",
    ultra_compact=True  # Use ultra-compact signatures
)

# tools is now a list of ToolDefinition objects
for tool in tools:
    print(f"{tool.compact_signature(ultra_compact=True)}")
    print(f"  → {tool.description}")
```

### Integration with Skills Generator

```python
from dietmcp.core.skills_generator import generate_skills
from dietmcp.openapi.parser import OpenAPIParser
from dietmcp.openapi.generator import OpenAPIToolGenerator
from dietmcp.config.loader import DietMcpConfig

# Parse and generate tools
parser = OpenAPIParser()
spec = parser.parse_spec("openapi.json")
generator = OpenAPIToolGenerator()
tools = generator.generate_tools(spec, server_name="myapi", ultra_compact=True)

# Tools are now compatible with skills_generator
# The generated tools can be cached and displayed like MCP tools
```

## Signature Formats

### Standard Compact (29 tokens/tool)

```
getUsers(id: str, ?limit: int, ?sort: str)
```

- Type annotations for all parameters
- `?` prefix for optional parameters
- Full type names (str, int, list[str], etc.)

### Ultra-Compact (13-15 tokens/tool)

```
getUsers(id, limit?, sort?: "asc" | "desc")
```

- Omit primitive types (str, int, bool, float)
- `?` suffix for optional parameters
- Shorthand for arrays: `[str]` instead of `list[str]`
- Show enum values: `"asc" | "desc"`
- Show object properties: `{name, tag}` instead of full schema

## Operation ID Generation

Operation IDs are automatically generated from the HTTP method and path:

| Path + Method | Operation ID |
|---------------|--------------|
| `GET /users` | `getUsers` |
| `GET /users/{id}` | `getUser` |
| `POST /users/{id}/posts` | `postUsersPosts` |
| `DELETE /users/{id}` | `deleteUser` |
| `GET /api/v1/users` | `getApiV1Users` |

Path parameters (e.g., `{id}`) are automatically excluded from operation IDs, following REST API conventions where path parameters are implied by the resource hierarchy.

## Parameter Handling

### Query Parameters

```python
OpenAPIEndpoint(
    path="/users",
    method="GET",
    parameters=[
        OpenAPIParameter(
            name="limit",
            in_="query",
            required=False,
            schema_={"type": "integer"}
        )
    ]
)
```

Generates:
```python
ToolDefinition(
    name="getUsers",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer"}
        },
        "required": []
    }
)
```

### Path Parameters

```python
OpenAPIEndpoint(
    path="/users/{id}",
    method="GET",
    parameters=[
        OpenAPIParameter(
            name="id",
            in_="path",
            required=True,
            schema_={"type": "string"}
        )
    ]
)
```

Path parameters are always required.

### Request Bodies

```python
OpenAPIEndpoint(
    path="/users",
    method="POST",
    request_body={
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    },
                    "required": ["name"]
                }
            }
        }
    }
)
```

Generates:
```python
ToolDefinition(
    name="createUser",
    input_schema={
        "type": "object",
        "properties": {
            "request_body": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "required": ["request_body"]
    }
)
```

## API Reference

### OpenAPIToolGenerator

```python
class OpenAPIToolGenerator:
    def generate_tools(
        self,
        spec: OpenAPISpec,
        server_name: str,
        ultra_compact: bool = False,
    ) -> list[ToolDefinition]:
        """Convert OpenAPI endpoints to tool definitions."""
```

### generate_signature

```python
def generate_signature(
    endpoint: OpenAPIEndpoint,
    ultra_compact: bool = False,
) -> str:
    """Generate an ultra-compact signature for an OpenAPI endpoint."""
```

Convenience function for generating signatures without creating a full `ToolDefinition`.

## Examples

See `examples/openapi_integration.py` for complete examples:

- Basic tool generation from OpenAPI spec
- Integration with skills_generator
- Signature format comparison
- Token savings demonstration

## Testing

Run the OpenAPI generator tests:

```bash
python -m pytest tests/test_openapi_generator.py -v
```

All tests should pass:
- `test_generate_simple_get_tool` - Basic GET endpoint
- `test_generate_post_tool_with_body` - POST with request body
- `test_generate_operation_id` - Operation ID generation
- `test_compact_signature` - Ultra-compact signatures
- `test_generate_multiple_tools` - Full spec conversion
- `test_array_parameter_type` - Array type handling
- `test_object_parameter_type` - Object type handling

## Design Decisions

### Why ToolDefinition Compatibility?

The generator produces `ToolDefinition` objects (the same model used for MCP tools) to ensure:
- Seamless integration with existing `skills_generator`
- Unified caching mechanism
- Consistent output format across protocols
- No code duplication in skill rendering

### Why Ultra-Compact Format?

Ultra-compact signatures reduce token usage by ~52%:
- Standard: ~29 tokens/tool
- Ultra-compact: ~13-15 tokens/tool

For a typical API with 50 endpoints, this saves ~700 tokens per skill summary.

### Why Request Body as Parameter?

Request bodies are added as a `request_body` parameter in input_schema to:
- Maintain consistency with JSON Schema structure
- Preserve complex object schemas (nested properties, validation)
- Allow validation of request body structure
- Support multiple content types (JSON, form data, etc.)

## Future Enhancements

Potential improvements:
- [ ] Security scheme mapping (API keys, OAuth)
- [ ] Response schema extraction for type hints
- [ ] Parameter grouping (path vs query vs header)
- [ ] Schema reference resolution ($ref)
- [ ] Multiple operation ID strategies (snake_case, kebab-case)
- [ ] Custom signature templates
