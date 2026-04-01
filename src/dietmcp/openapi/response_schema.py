"""Response schema extraction for OpenAPI endpoints."""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResponseSchema:
    """Extracted response schema information."""

    content_type: str
    """Content type (e.g., "application/json")."""

    schema: Dict[str, Any]
    """Schema definition."""

    is_array: bool = False
    """Whether response is an array."""

    array_item_schema: Optional[Dict[str, Any]] = None
    """Schema for array items (if is_array=True)."""

    description: Optional[str] = None
    """Schema description."""


def extract_response_schema(
    response_def: Dict[str, Any],
    content_type: str = "application/json"
) -> ResponseSchema:
    """Extract response schema from OpenAPI response definition.

    Args:
        response_def: OpenAPI response definition
        content_type: Primary content type

    Returns:
        Extracted schema information
    """
    # Check for content field
    if "content" not in response_def:
        # No content defined
        return ResponseSchema(
            content_type=content_type,
            schema={},
            is_array=False,
            description="No content defined"
        )

    # Get schema for primary content type
    content_defs = response_def["content"]
    primary_def = content_defs.get(content_type)

    if not primary_def:
        # Try fallback content types
        for ct in content_defs:
            primary_def = content_defs[ct]
            if primary_def:
                break

    if not primary_def or "schema" not in primary_def:
        return ResponseSchema(
            content_type=content_type,
            schema={},
            is_array=False,
            description="No schema defined"
        )

    schema = primary_def["schema"]

    # Check for $ref
    if "$ref" in schema:
        # Extract reference
        ref = schema["$ref"]
        if ref.startswith("#/components/schemas/"):
            schema_name = ref.split("/")[-1]
            return ResponseSchema(
                content_type=content_type,
                schema={"type": "object", "$ref": schema_name},
                is_array=False,
                description=f"Reference to {schema_name}"
            )

    # Check if it's an array
    is_array = schema.get("type") == "array"
    array_item_schema = None

    if is_array and "items" in schema:
        array_item_schema = schema["items"]

    return ResponseSchema(
        content_type=content_type,
        schema=schema,
        is_array=is_array,
        array_item_schema=array_item_schema,
        description=schema.get("description")
    )


def format_schema_for_tool_description(schema: Dict[str, Any]) -> str:
    """Format schema for tool description.

    Args:
        schema: Schema definition

    Returns:
        Formatted schema description
    """
    schema_type = schema.get("type", "any")

    if schema_type == "object":
        props = schema.get("properties", {})
        if props:
            prop_names = list(props.keys())[:3]  # First 3 properties
            if len(props) > 3:
                prop_names.append("...")
            return f"object{{{', '.join(prop_names)}}}"
        return "object"

    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = items.get("type", "any")
        return f"array[{item_type}]"

    elif schema_type in ["string", "integer", "number", "boolean"]:
        return schema_type

    elif schema_type == "any":
        return "any"

    return "unknown"
