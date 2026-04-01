"""TOON-like formatter: columnar encoding for uniform arrays.

Achieves 40-60% compression on tabular data by eliminating repetitive
JSON keys and using position-based encoding.
"""

from __future__ import annotations

import json
from typing import Any

from dietmcp.models.response import TunedResponse
from dietmcp.models.tool import ToolResult

# Maximum count to prevent DoS attacks via malicious TOON responses
# This limit prevents excessive memory allocation from crafted inputs
MAX_TOON_COUNT = 100_000

# Security: Maximum JSON size to prevent DoS via memory exhaustion
MAX_JSON_SIZE = 1_000_000  # 1MB limit


class ToonFormatter:
    """Formatter that produces TOON-like columnar output.

    Detects uniform arrays (objects with identical keys) and encodes them
    in a compact columnar format: [count]{keys}: values

    Falls back to minified JSON for non-tabular data.
    """

    def format(self, result: ToolResult, max_size: int) -> TunedResponse:
        """Format tool result using TOON encoding."""
        data = _extract_data(result)

        if not isinstance(data, list):
            # Not an array - use minified JSON
            return _fallback_format(result, max_size)

        if not data:
            # Empty array
            text = "[]"
            return TunedResponse(
                format_name="toon",
                content=text,
                is_error=result.is_error,
                was_truncated=False,
            )

        # Check if uniform array (all objects with same keys)
        if not _is_uniform_object_array(data):
            return _fallback_format(result, max_size)

        # Encode in TOON format
        text = _encode_toon(data)
        was_truncated = len(text) > max_size

        if was_truncated:
            text = text[:max_size]

        return TunedResponse(
            format_name="toon",
            content=text,
            is_error=result.is_error,
            was_truncated=was_truncated,
        )


def _extract_data(result: ToolResult) -> Any:
    """Extract structured data from tool result."""
    # Try parsing text content as JSON
    text = result.text_content()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try using raw response
    if result.raw:
        # Look for arrays in raw response
        for key, value in result.raw.items():
            if isinstance(value, list):
                return value

    return None


def _is_uniform_object_array(data: list[Any]) -> bool:
    """Check if data is a uniform array of objects with identical keys."""
    if not data:
        return False

    if not isinstance(data[0], dict):
        return False

    # Get keys from first object
    first_keys = set(data[0].keys())

    # Check all objects have same keys
    for item in data[1:]:
        if not isinstance(item, dict):
            return False
        if set(item.keys()) != first_keys:
            return False

    return True


def _encode_toon(data: list[dict]) -> str:
    """Encode a uniform object array in TOON format.

    Format: [count]{key1,key2,...}: value1,value2,...

    Example:
        Input:  [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        Output: [2]{id,name}: 1,Alice,2,Bob
    """
    if not data:
        return "[]"

    # Extract column headers (keys)
    keys = list(data[0].keys())
    key_str = ",".join(keys)

    # Extract values in column-major order
    # For [count]{a,b}: 1,2,3,4 means [{a:1,b:2}, {a:3,b:4}]
    values: list[str] = []
    for obj in data:
        for key in keys:
            value = obj.get(key)
            values.append(_serialize_value(value))

    value_str = ",".join(values)

    return f"[{len(data)}]{{{key_str}}}: {value_str}"


def _serialize_value(value: Any) -> str:
    """Serialize a single value for TOON encoding.

    Strings containing special characters are escaped with backticks.
    Null values are represented as empty strings.
    """
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        # Preserve the original string representation to avoid losing precision
        # or trailing zeros
        return repr(value)

    if isinstance(value, str):
        # Escape strings with special characters
        if any(c in value for c in [",", ":", "{", "}", "[", "]", "`", "\n", "\t"]):
            # Backtick escape - replace backticks with double backticks
            escaped = value.replace("`", "``")
            return f"`{escaped}`"
        return value

    if isinstance(value, (list, dict)):
        # Nested structures - use compact JSON
        return json.dumps(value, separators=(",", ":"))

    return str(value)


def _deserialize_value(s: str) -> Any:
    """Deserialize a single value from TOON encoding."""
    if s == "":
        return None

    if s == "true":
        return True

    if s == "false":
        return False

    # Check for backtick-escaped string
    if s.startswith("`") and s.endswith("`"):
        # Remove outer backticks and unescape
        content = s[1:-1].replace("``", "`")
        return content

    # Try parsing as number
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        pass

    # Try parsing as JSON (for nested structures)
    try:
        # Security: Check size before deserialization to prevent DoS
        if len(s) > MAX_JSON_SIZE:
            raise ValueError(
                f"JSON value too large: {len(s)} bytes (max {MAX_JSON_SIZE})"
            )
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        pass

    # Default to string
    return s


def _decode_toon(text: str) -> list[dict]:
    """Decode TOON format back to list of dicts.

    Raises ValueError if format is invalid.
    """
    text = text.strip()

    if text == "[]":
        return []

    # Parse format: [count]{keys}: values
    if not text.startswith("["):
        raise ValueError("Invalid TOON format: missing opening bracket")

    bracket_end = text.index("]")
    count_part = text[1:bracket_end]

    try:
        count = int(count_part)
    except ValueError:
        raise ValueError(f"Invalid TOON format: invalid count '{count_part}'")

    if count > MAX_TOON_COUNT:
        raise ValueError(
            f"TOON count {count} exceeds maximum {MAX_TOON_COUNT}. "
            f"This may indicate a malicious response or data format error."
        )

    if not text[bracket_end + 1:].startswith("{"):
        raise ValueError("Invalid TOON format: missing opening brace for keys")

    brace_end = text.index("}", bracket_end)
    keys_str = text[bracket_end + 2:brace_end]
    keys = keys_str.split(",") if keys_str else []

    if not text[brace_end + 1:].startswith(": "):
        raise ValueError("Invalid TOON format: missing value separator")

    values_str = text[brace_end + 3:]
    values = _split_values(values_str) if values_str else []

    # Reconstruct objects
    result = []
    for i in range(count):
        obj = {}
        for j, key in enumerate(keys):
            value_idx = i * len(keys) + j
            if value_idx < len(values):
                obj[key] = _deserialize_value(values[value_idx])
            else:
                obj[key] = None
        result.append(obj)

    return result


def _split_values(text: str) -> list[str]:
    """Split values by comma, respecting backtick-escaped strings.

    Backtick-escaped strings are treated as single values even if they contain commas.
    Double backticks inside escaped strings are unescaped.
    """
    values = []
    current = []
    in_escape = False

    i = 0
    while i < len(text):
        char = text[i]

        if char == "`" and not in_escape:
            # Start of escape sequence
            in_escape = True
            current.append(char)
            i += 1
        elif char == "`" and in_escape:
            # Check if this is an escaped backtick (double backtick)
            if i + 1 < len(text) and text[i + 1] == "`":
                # Double backtick - treat as single backtick in the escaped string
                current.append(char)
                current.append(char)  # Add both backticks
                i += 2
            else:
                # End of escape sequence
                in_escape = False
                current.append(char)
                i += 1
        elif char == "," and not in_escape:
            # Comma outside escape - split here
            values.append("".join(current))
            current = []
            i += 1
        else:
            # Regular character
            current.append(char)
            i += 1

    # Add last value
    if current:
        values.append("".join(current))

    return values


def _fallback_format(result: ToolResult, max_size: int) -> TunedResponse:
    """Fallback to minified JSON for non-tabular data."""
    # Try to use the text content directly if it's valid JSON
    text = result.text_content()

    # Validate it's valid JSON
    try:
        parsed = json.loads(text)
        # Re-serialize with minified format
        text = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        # If not valid JSON, use raw response or wrap text
        if result.raw:
            cleaned = _strip_nulls(result.raw)
            text = json.dumps(cleaned, separators=(",", ":"), ensure_ascii=False)
        else:
            # Wrap plain text in content field
            text = json.dumps({"content": text}, separators=(",", ":"), ensure_ascii=False)

    was_truncated = len(text) > max_size
    if was_truncated:
        text = text[:max_size]

    return TunedResponse(
        format_name="toon",
        content=text,
        is_error=result.is_error,
        was_truncated=was_truncated,
    )


def _strip_nulls(obj: Any) -> Any:
    """Recursively remove None/null values from dicts."""
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(item) for item in obj]
    return obj
