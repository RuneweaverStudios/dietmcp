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

    def compact_signature(self) -> str:
        """Generate a compact type signature like: tool(path: str, ?recursive: bool)."""
        props = self.input_schema.get("properties", {})
        required = set(self.required_params())
        parts = []
        for param_name, param_schema in props.items():
            type_hint = _json_type_to_hint(param_schema)
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


def _json_type_to_hint(schema: dict) -> str:
    """Convert a JSON Schema type to a compact type hint."""
    json_type = schema.get("type", "any")
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
        item_type = _json_type_to_hint(schema["items"])
        return f"list[{item_type}]"

    if "enum" in schema:
        values = " | ".join(f'"{v}"' for v in schema["enum"][:5])
        if len(schema["enum"]) > 5:
            values += " | ..."
        return values

    return base
