"""Tool definition and result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ToolDefinition(BaseModel):
    """Immutable representation of an MCP tool's schema."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict
    server_name: str

    def parameter_count(self) -> int:
        props = self.input_schema.get("properties", {})
        return len(props)

    def required_params(self) -> list[str]:
        return list(self.input_schema.get("required", []))

    def optional_params(self) -> list[str]:
        all_params = list(self.input_schema.get("properties", {}).keys())
        required = set(self.required_params())
        return [p for p in all_params if p not in required]

    def compact_signature(self, ultra_compact: bool = False) -> str:
        """Generate a compact type signature.

        Args:
            ultra_compact: If True, use ultra-compact format (13-15 tokens/tool).
                          If False, use standard compact format (29 tokens/tool).

        Returns:
            Compact signature string.

        Examples:
            Standard: tool(path: str, ?recursive: bool)
            Ultra: tool(path, recursive?)
        """
        props = self.input_schema.get("properties", {})
        required = set(self.required_params())
        parts = []
        for param_name, param_schema in props.items():
            if ultra_compact:
                # Ultra-compact format: param? for optional, omit primitive types
                is_optional = param_name not in required
                type_hint = _json_type_to_hint(param_schema, ultra_compact=True)
                if type_hint:
                    # Complex type: param: [type] or param?: [type]
                    suffix = "?" if is_optional else ""
                    parts.append(f"{param_name}{suffix}: {type_hint}")
                else:
                    # Primitive type: omit type hint, use ? suffix for optional
                    suffix = "?" if is_optional else ""
                    parts.append(f"{param_name}{suffix}")
            else:
                # Standard compact format: ?param: type
                type_hint = _json_type_to_hint(param_schema, ultra_compact=False)
                prefix = "" if param_name in required else "?"
                parts.append(f"{prefix}{param_name}: {type_hint}")
        params_str = ", ".join(parts)
        return f"{self.name}({params_str})"


class ToolResult(BaseModel):
    """Immutable representation of an MCP tool call response."""

    model_config = ConfigDict(frozen=True)

    content: list[dict]
    is_error: bool = False
    raw: dict = {}

    def text_content(self) -> str:
        """Extract concatenated text from content blocks."""
        parts = []
        for block in self.content:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)

    def total_size(self) -> int:
        return len(self.text_content())


def _json_type_to_hint(schema: dict, ultra_compact: bool = False) -> str:
    """Convert a JSON Schema type to a compact type hint.

    Args:
        schema: JSON Schema property definition.
        ultra_compact: If True, omit primitive types and use shorthand notation.

    Returns:
        Type hint string, or empty string for primitive types in ultra-compact mode.

    Examples:
        Standard: "str", "list[str]", "active | inactive"
        Ultra: "", "[str]", "active | inactive"
    """
    json_type = schema.get("type", "any")

    # Enums always show values in both modes (check before primitive check)
    if "enum" in schema:
        values = " | ".join(f'"{v}"' for v in schema["enum"][:5])
        if len(schema["enum"]) > 5:
            values += " | ..."
        return values

    # Primitive types (omit in ultra-compact mode)
    primitive_types = {"string", "integer", "number", "boolean"}
    if ultra_compact and json_type in primitive_types:
        # Return empty string to signal "omit type hint"
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
            # Ultra-compact: [str] instead of list[str]
            # Empty item_type means primitive, so just use []
            if item_type:
                return f"[{item_type}]"
            else:
                # Array of primitives - infer from items schema
                item_json_type = schema["items"].get("type", "any")
                item_base = type_map.get(item_json_type, item_json_type)
                return f"[{item_base}]"
        else:
            return f"list[{item_type}]"

    # Object type
    if json_type == "object" and ultra_compact:
        # Show field names if properties exist
        if "properties" in schema:
            fields = ", ".join(list(schema["properties"].keys())[:3])
            if len(schema["properties"]) > 3:
                fields += ", ..."
            return f"{{{fields}}}"
        return "{}"

    return base
