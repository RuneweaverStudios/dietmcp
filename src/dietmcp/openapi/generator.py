"""OpenAPI tool generation for unified MCP tool definitions.

DEV NOTES:
- Converts OpenAPI endpoints to ToolDefinition objects for integration with
  the skills_generator system.
- Operation ID generation: HTTP method + path (e.g., GET /users/{id} -> getUsersById)
- Parameter mapping: OpenAPI params -> JSON Schema input_schema
- Ultra-compact support: Generates 13-15 token signatures per tool
- Request body handling: Merges into input_schema as "request_body" parameter
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from dietmcp.models.openapi import OpenAPIEndpoint, OpenAPIParameter, OpenAPISpec
from dietmcp.models.tool import ToolDefinition


class OperationIDStrategy(str, Enum):
    """Operation ID generation strategies."""

    AUTO = "auto"  # Use operationId from spec or generate
    PATH_METHOD = "path_method"  # {path}_{method}
    PATH_LOWER = "path_lower"  # /users/{id} -> users
    CAMEL_CASE = "camel_case"  # /users/{id} -> usersId
    SNAKE_CASE = "snake_case"  # /users/{id} -> users_id
    KEBAB_CASE = "kebab_case"  # /users/{id} -> users-id


def generate_operation_id(
    endpoint: OpenAPIEndpoint,
    strategy: OperationIDStrategy = OperationIDStrategy.AUTO,
) -> str:
    """Generate operation ID using specified strategy.

    Args:
        endpoint: OpenAPI endpoint
        strategy: Generation strategy

    Returns:
        Generated operation ID

    Examples:
        >>> endpoint = OpenAPIEndpoint(path="/users/{id}", method="GET")
        >>> generate_operation_id(endpoint, OperationIDStrategy.PATH_METHOD)
        'users_id_get'
        >>> generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE)
        'getUsers'
        >>> generate_operation_id(endpoint, OperationIDStrategy.SNAKE_CASE)
        'users_id'
    """
    # If spec has operationId and strategy is AUTO, use it
    if strategy == OperationIDStrategy.AUTO and endpoint.operation_id:
        return endpoint.operation_id

    path = endpoint.path
    method = endpoint.method.lower()

    # Remove path parameters for cleaner IDs
    path_clean = re.sub(r"\{[^}]+\}", "", path)
    path_clean = path_clean.strip("/")

    if strategy == OperationIDStrategy.AUTO:
        # Auto falls back to CAMEL_CASE if no operationId in spec
        if not endpoint.operation_id:
            return _generate_camel_case_operation_id(path_clean, method)
        return endpoint.operation_id

    elif strategy == OperationIDStrategy.PATH_METHOD:
        # Replace / with _ and append method (preserve original case)
        path_part = path_clean.replace("/", "_") if path_clean else "root"
        return f"{path_part}_{method}" if path_clean else method

    elif strategy == OperationIDStrategy.PATH_LOWER:
        # Lowercase, replace / with _, no method suffix
        return path_clean.replace("/", "_").lower() if path_clean else method

    elif strategy == OperationIDStrategy.PATH_LOWER:
        # Lowercase, replace / with _, no method suffix (removes parameters)
        return path_clean.replace("/", "_").lower() if path_clean else method

    elif strategy == OperationIDStrategy.CAMEL_CASE:
        # /users/{id} -> getUsers
        return _generate_camel_case_operation_id(path_clean, method)

    elif strategy == OperationIDStrategy.SNAKE_CASE:
        # /users/{id} -> users_id (lowercase, keeps parameter names, no method)
        # Replace path parameters with underscore-prefixed parameter names
        snake_path = re.sub(r'\{([^}]+)\}', r'_\1', endpoint.path)
        snake_path = snake_path.strip('/').replace('/', '_').lower()
        # Clean up double underscores
        snake_path = re.sub(r'_+', '_', snake_path).strip('_')
        return snake_path if snake_path else method

    elif strategy == OperationIDStrategy.KEBAB_CASE:
        # /users/{id} -> users-id
        return path_clean.replace("/", "-").lower() if path_clean else method

    else:
        # Default to path_method
        path_part = path_clean.replace("/", "_") if path_clean else "root"
        return f"{path_part}_{method}"


def _generate_camel_case_operation_id(path_clean: str, method: str) -> str:
    """Generate camelCase operation ID from path and method.

    Args:
        path_clean: Path with parameters removed, leading/trailing slashes stripped
        method: HTTP method in lowercase

    Returns:
        camelCase operation ID like "getUsers" or "getApiV1Users"
    """
    if not path_clean:
        # Root path operation
        return method

    # Split path and capitalize each part
    parts = [p for p in path_clean.split("/") if p]
    if not parts:
        return method

    # Join with title case and lowercase first letter
    resource = "".join(p.title() for p in parts)
    resource = resource[0].lower() + resource[1:] if resource else "root"

    # Prefix with HTTP method (capitalize first letter of resource)
    return f"{method}{resource[0].upper()}{resource[1:]}"


class OpenAPIToolGenerator:
    """Convert OpenAPI endpoints to unified ToolDefinition objects.

    This generator bridges OpenAPI specs and the MCP tool system, enabling
    HTTP APIs to be exposed as dietmcp skills with the same compact formatting
    and caching as native MCP servers.
    """

    def __init__(
        self,
        operation_id_strategy: OperationIDStrategy = OperationIDStrategy.AUTO,
    ) -> None:
        """Initialize the generator with an operation ID strategy.

        Args:
            operation_id_strategy: Strategy for generating operation IDs.
        """
        self.operation_id_strategy = operation_id_strategy

    def generate_tools(
        self,
        spec: OpenAPISpec,
        server_name: str,
        ultra_compact: bool = False,
    ) -> list[ToolDefinition]:
        """Convert OpenAPI endpoints to tool definitions.

        Args:
            spec: Parsed OpenAPI specification.
            server_name: Name for the tool source (e.g., "petstore", "github").
            ultra_compact: If True, use ultra-compact signatures (13-15 tokens/tool).

        Returns:
            List of ToolDefinition objects, one per endpoint.
        """
        tools = []
        for endpoint in spec.endpoints:
            tool = self._generate_tool(endpoint, server_name, ultra_compact)
            if tool:
                tools.append(tool)
        return tools

    def _generate_tool(
        self,
        endpoint: OpenAPIEndpoint,
        server_name: str,
        ultra_compact: bool,
    ) -> ToolDefinition | None:
        """Generate a ToolDefinition from a single endpoint.

        Args:
            endpoint: OpenAPI endpoint definition.
            server_name: Tool source name.
            ultra_compact: Signature format preference.

        Returns:
            ToolDefinition or None if endpoint lacks required fields.
        """
        # Generate operation ID using configured strategy
        operation_id = generate_operation_id(endpoint, self.operation_id_strategy)

        # Build description from summary/description
        description = endpoint.summary or endpoint.description or ""
        if not description:
            # Fallback: method + path
            description = f"{endpoint.method} {endpoint.path}"

        # Build input schema from parameters and request body
        input_schema = self._build_input_schema(endpoint)

        return ToolDefinition(
            name=operation_id,
            description=description,
            input_schema=input_schema,
            server_name=server_name,
        )

    def _generate_operation_id(self, endpoint: OpenAPIEndpoint) -> str:
        """Generate operation ID from method and path (legacy method).

        Deprecated: Use generate_operation_id() function with strategy instead.

        Examples:
            GET /users -> getUsers
            POST /users/{id}/posts -> createUsersPosts
            GET /api/v1/users/{id} -> getApiV1Users
        """
        return generate_operation_id(endpoint, OperationIDStrategy.CAMEL_CASE)

    def _build_input_schema(self, endpoint: OpenAPIEndpoint) -> dict[str, Any]:
        """Build JSON Schema input_schema from OpenAPI parameters and request body.

        Args:
            endpoint: OpenAPI endpoint definition.

        Returns:
            JSON Schema compatible input_schema dict.
        """
        properties = {}
        required = []

        # Process parameters (query, path, header, cookie)
        for param in endpoint.parameters:
            param_schema = self._convert_param_schema(param)
            properties[param.name] = param_schema
            if param.required:
                required.append(param.name)

        # Process request body (POST/PUT/PATCH)
        if endpoint.request_body:
            # Extract content schema (default to application/json)
            body_schema = self._extract_body_schema(endpoint.request_body)
            if body_schema:
                properties["request_body"] = body_schema
                # Request body is typically required for POST/PUT/PATCH
                if endpoint.method in ("POST", "PUT", "PATCH"):
                    required.append("request_body")

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def _convert_param_schema(self, param: OpenAPIParameter) -> dict[str, Any]:
        """Convert OpenAPI parameter to JSON Schema property.

        Args:
            param: OpenAPI parameter definition.

        Returns:
            JSON Schema property definition.
        """
        return _convert_param_schema(param)

    def _extract_body_schema(self, request_body: dict[str, Any]) -> dict[str, Any] | None:
        """Extract request body schema from OpenAPI request body object.

        Args:
            request_body: OpenAPI request body definition.

        Returns:
            JSON Schema for the body, or None if not found.
        """
        return _extract_body_schema(request_body)


def generate_signature(
    endpoint: OpenAPIEndpoint,
    ultra_compact: bool = False,
    operation_id_strategy: OperationIDStrategy = OperationIDStrategy.AUTO,
) -> str:
    """Generate an ultra-compact signature for an OpenAPI endpoint.

    This is a convenience function for generating signatures without
    creating a full ToolDefinition.

    Args:
        endpoint: OpenAPI endpoint definition.
        ultra_compact: If True, use ultra-compact format.
        operation_id_strategy: Strategy for generating operation ID.

    Returns:
        Signature string like "getUsers(id, limit?)" or "getUsers(id: str, ?limit: int)"

    Examples:
        Ultra-compact: getUsers(id, limit?, sort?)
        Standard: getUsers(id: str, ?limit: int, ?sort: str)
    """
    operation_id = generate_operation_id(endpoint, operation_id_strategy)

    # Build temp input schema for signature generation
    properties = {}
    required = []

    for param in endpoint.parameters:
        param_schema = param.schema_ or {"type": "string"}
        properties[param.name] = param_schema
        if param.required:
            required.append(param.name)

    if endpoint.request_body:
        body_schema = _extract_body_schema(endpoint.request_body)
        if body_schema:
            properties["request_body"] = body_schema
            if endpoint.method in ("POST", "PUT", "PATCH"):
                required.append("request_body")

    # Generate signature parts
    parts = []
    for param_name, param_schema in properties.items():
        is_required = param_name in required

        if ultra_compact:
            # Ultra-compact: param? for optional, omit primitive types
            type_hint = _json_type_to_hint(param_schema, ultra_compact=True)
            if type_hint:
                suffix = "?" if not is_required else ""
                parts.append(f"{param_name}{suffix}: {type_hint}")
            else:
                suffix = "?" if not is_required else ""
                parts.append(f"{param_name}{suffix}")
        else:
            # Standard: ?param: type
            type_hint = _json_type_to_hint(param_schema, ultra_compact=False)
            prefix = "" if is_required else "?"
            parts.append(f"{prefix}{param_name}: {type_hint}")

    params_str = ", ".join(parts)
    return f"{operation_id}({params_str})"


def _json_type_to_hint(schema: dict, ultra_compact: bool = False) -> str:
    """Convert a JSON Schema type to a compact type hint.

    This is a simplified version of ToolDefinition._json_type_to_hint
    for use in standalone signature generation.

    Args:
        schema: JSON Schema property definition.
        ultra_compact: If True, omit primitive types and use shorthand.

    Returns:
        Type hint string, or empty string for primitive types in ultra-compact mode.
    """
    json_type = schema.get("type", "any")

    # Enums always show values
    if "enum" in schema:
        values = " | ".join(f'"{v}"' for v in schema["enum"][:5])
        if len(schema["enum"]) > 5:
            values += " | ..."
        return values

    # Primitive types (omit in ultra-compact mode)
    primitive_types = {"string", "integer", "number", "boolean"}
    if ultra_compact and json_type in primitive_types:
        return ""

    type_map = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }
    base = type_map.get(json_type, json_type)

    if json_type == "array" and "items" in schema:
        item_type = _json_type_to_hint(schema["items"], ultra_compact=ultra_compact)
        if ultra_compact:
            if item_type:
                return f"[{item_type}]"
            else:
                item_json_type = schema["items"].get("type", "any")
                item_base = type_map.get(item_json_type, item_json_type)
                return f"[{item_base}]"
        else:
            return f"list[{item_type}]"

    # Object type
    if json_type == "object" and ultra_compact:
        if "properties" in schema:
            fields = ", ".join(list(schema["properties"].keys())[:3])
            if len(schema["properties"]) > 3:
                fields += ", ..."
            return f"{{{fields}}}"
        return "{}"

    return base


def _convert_param_schema(param: OpenAPIParameter) -> dict[str, Any]:
    """Convert OpenAPI parameter to JSON Schema property.

    Args:
        param: OpenAPI parameter definition.

    Returns:
        JSON Schema property definition.
    """
    # Start with parameter's schema if available
    if param.schema_:
        schema = param.schema_.copy()
    else:
        # Fallback: infer from description or default to string
        schema = {"type": "string"}

    # Add description if available
    if param.description:
        schema["description"] = param.description

    # Add example if available
    if param.example is not None:
        schema["example"] = param.example

    # Ensure type is present
    if "type" not in schema:
        schema["type"] = "string"

    return schema


def _extract_body_schema(request_body: dict[str, Any]) -> dict[str, Any] | None:
    """Extract request body schema from OpenAPI request body object.

    Args:
        request_body: OpenAPI request body definition.

    Returns:
        JSON Schema for the body, or None if not found.
    """
    # Try application/json first
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    if not json_content:
        # Fallback to first content type
        first_content = next(iter(content.values()), {})
        json_content = first_content

    schema = json_content.get("schema")
    if schema:
        # Add description from request body if available
        result = schema.copy()
        if "description" in request_body:
            result["description"] = request_body["description"]
        return result

    return None
