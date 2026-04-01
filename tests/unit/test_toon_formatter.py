"""Tests for TOON formatter."""

from __future__ import annotations

import json

import pytest

from dietmcp.formatters.toon_formatter import (
    ToonFormatter,
    _decode_toon,
    _deserialize_value,
    _encode_toon,
    _is_uniform_object_array,
    _serialize_value,
)
from dietmcp.models.tool import ToolResult


class TestToonFormatter:
    """Test the main ToonFormatter class."""

    def test_uniform_object_array(self):
        """Test encoding a uniform array of objects."""
        data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert response.was_truncated is False
        # Should start with [3]{id,name,email}:
        assert "[3]{id,name,email}:" in response.content
        assert "alice@example.com" in response.content

    def test_empty_array(self):
        """Test encoding an empty array."""
        result = ToolResult(content=[{"type": "text", "text": "[]"}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert response.content == "[]"
        assert response.was_truncated is False

    def test_single_object(self):
        """Test encoding an array with one object."""
        data = [{"id": 1, "name": "Alice"}]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert "[1]{id,name}:" in response.content
        assert "Alice" in response.content

    def test_non_uniform_array_fallback(self):
        """Test that non-uniform arrays fall back to minified JSON."""
        data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "age": 30},  # Different keys
            {"id": 3, "name": "Charlie", "email": "charlie@example.com"},  # Extra key
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        # Should be minified JSON, not TOON format
        assert "[{" in response.content or '["' in response.content
        assert "[" not in response.content or response.content.startswith("[")

    def test_primitive_array_fallback(self):
        """Test that primitive arrays fall back to minified JSON."""
        data = [1, 2, 3, 4, 5]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert response.content == "[1,2,3,4,5]"

    def test_mixed_array_fallback(self):
        """Test that mixed-type arrays fall back to minified JSON."""
        data = [{"id": 1}, "string", 123, None]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        # Should be minified JSON
        assert response.content.startswith("[")

    def test_object_fallback(self):
        """Test that non-array objects fall back to minified JSON."""
        data = {"users": [{"id": 1}, {"id": 2}], "count": 2}
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        # Should be minified JSON with outer object
        assert response.content.startswith("{")

    def test_null_values(self):
        """Test encoding objects with null values."""
        data = [
            {"id": 1, "name": "Alice", "email": None},
            {"id": 2, "name": None, "email": "bob@example.com"},
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert "[2]{id,name,email}:" in response.content

    def test_boolean_values(self):
        """Test encoding boolean values."""
        data = [
            {"id": 1, "active": True},
            {"id": 2, "active": False},
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert "[2]{id,active}:" in response.content
        assert "true" in response.content
        assert "false" in response.content

    def test_numeric_values(self):
        """Test encoding numeric values (int and float)."""
        data = [
            {"id": 1, "price": 19.99, "count": 5},
            {"id": 2, "price": 29.5, "count": 10},
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert "[2]{id,price,count}:" in response.content
        assert "19.99" in response.content
        assert "29.5" in response.content

    def test_special_character_escaping(self):
        """Test that strings with special characters are escaped."""
        data = [
            {"id": 1, "text": "Hello, world!"},
            {"id": 2, "text": "Test: [value]"},
            {"id": 3, "text": "With{braces}"},
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        # Should use backtick escaping for strings with special chars
        assert "`" in response.content

    def test_nested_structures(self):
        """Test encoding objects with nested structures."""
        data = [
            {"id": 1, "tags": ["a", "b"]},
            {"id": 2, "tags": ["c", "d"]},
        ]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.format_name == "toon"
        assert "[2]{id,tags}:" in response.content
        # Nested arrays should be JSON-encoded
        assert '["a","b"]' in response.content or '["c","d"]' in response.content

    def test_truncation(self):
        """Test that large responses are truncated."""
        # Generate a large array
        data = [{"id": i, "name": f"User{i}", "email": f"user{i}@example.com"} for i in range(1000)]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}])

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=500)

        assert response.format_name == "toon"
        assert response.was_truncated is True
        assert len(response.content) <= 500

    def test_is_error_propagated(self):
        """Test that error flag is preserved."""
        data = [{"id": 1, "name": "Alice"}]
        text = json.dumps(data)
        result = ToolResult(content=[{"type": "text", "text": text}], is_error=True)

        fmt = ToonFormatter()
        response = fmt.format(result, max_size=10000)

        assert response.is_error is True


class TestIsUniformObjectArray:
    """Test uniform array detection."""

    def test_uniform_array(self):
        """Test detection of uniform array."""
        data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        assert _is_uniform_object_array(data) is True

    def test_non_uniform_different_keys(self):
        """Test detection of non-uniform array (different keys)."""
        data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "age": 30},
        ]
        assert _is_uniform_object_array(data) is False

    def test_non_uniform_missing_keys(self):
        """Test detection of non-uniform array (missing keys)."""
        data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob"},
        ]
        assert _is_uniform_object_array(data) is False

    def test_empty_array(self):
        """Test empty array."""
        assert _is_uniform_object_array([]) is False

    def test_primitive_array(self):
        """Test array of primitives."""
        assert _is_uniform_object_array([1, 2, 3]) is False

    def test_mixed_array(self):
        """Test mixed-type array."""
        assert _is_uniform_object_array([{"a": 1}, "string", 123]) is False


class TestSerializeValue:
    """Test value serialization."""

    def test_null(self):
        assert _serialize_value(None) == ""

    def test_boolean_true(self):
        assert _serialize_value(True) == "true"

    def test_boolean_false(self):
        assert _serialize_value(False) == "false"

    def test_integer(self):
        assert _serialize_value(42) == "42"

    def test_float(self):
        assert _serialize_value(3.14) == "3.14"

    def test_simple_string(self):
        assert _serialize_value("hello") == "hello"

    def test_string_with_comma(self):
        assert _serialize_value("hello, world") == "`hello, world`"

    def test_string_with_colon(self):
        assert _serialize_value("key: value") == "`key: value`"

    def test_string_with_braces(self):
        assert _serialize_value("test{value}") == "`test{value}`"

    def test_string_with_brackets(self):
        assert _serialize_value("test[value]") == "`test[value]`"

    def test_string_with_backtick(self):
        # Backticks should be doubled
        assert _serialize_value("test`value") == "`test``value`"

    def test_string_with_newline(self):
        assert _serialize_value("line1\nline2") == "`line1\nline2`"

    def test_list(self):
        assert _serialize_value([1, 2, 3]) == "[1,2,3]"

    def test_dict(self):
        assert _serialize_value({"a": 1, "b": 2}) == '{"a":1,"b":2}'


class TestDeserializeValue:
    """Test value deserialization."""

    def test_empty_string(self):
        assert _deserialize_value("") is None

    def test_boolean_true(self):
        assert _deserialize_value("true") is True

    def test_boolean_false(self):
        assert _deserialize_value("false") is False

    def test_integer(self):
        assert _deserialize_value("42") == 42

    def test_float(self):
        assert _deserialize_value("3.14") == 3.14

    def test_simple_string(self):
        assert _deserialize_value("hello") == "hello"

    def test_escaped_string(self):
        assert _deserialize_value("`hello, world`") == "hello, world"

    def test_escaped_string_with_backtick(self):
        assert _deserialize_value("`test``value`") == "test`value"

    def test_json_list(self):
        assert _deserialize_value("[1,2,3]") == [1, 2, 3]

    def test_json_dict(self):
        result = _deserialize_value('{"a":1,"b":2}')
        assert result == {"a": 1, "b": 2}


class TestEncodeToon:
    """Test TOON encoding."""

    def test_empty_array(self):
        assert _encode_toon([]) == "[]"

    def test_single_object(self):
        data = [{"id": 1, "name": "Alice"}]
        result = _encode_toon(data)
        assert result == "[1]{id,name}: 1,Alice"

    def test_multiple_objects(self):
        data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        result = _encode_toon(data)
        assert result == "[2]{id,name}: 1,Alice,2,Bob"

    def test_with_nulls(self):
        data = [
            {"id": 1, "name": "Alice", "email": None},
            {"id": 2, "name": None, "email": "bob@example.com"},
        ]
        result = _encode_toon(data)
        assert "[2]{id,name,email}:" in result
        # Check that nulls are represented as empty strings
        parts = result.split(": ")[1].split(",")
        assert parts[2] == ""  # Alice's email
        assert parts[4] == ""  # Bob's name


class TestDecodeToon:
    """Test TOON decoding."""

    def test_empty_array(self):
        assert _decode_toon("[]") == []

    def test_single_object(self):
        result = _decode_toon("[1]{id,name}: 1,Alice")
        assert result == [{"id": 1, "name": "Alice"}]

    def test_multiple_objects(self):
        result = _decode_toon("[2]{id,name}: 1,Alice,2,Bob")
        assert result == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

    def test_with_nulls(self):
        result = _decode_toon("[2]{id,name,email}: 1,Alice,,2,,bob@example.com")
        assert result == [
            {"id": 1, "name": "Alice", "email": None},
            {"id": 2, "name": None, "email": "bob@example.com"},
        ]

    def test_invalid_format_missing_bracket(self):
        with pytest.raises(ValueError, match="missing opening bracket"):
            _decode_toon("2]{id,name}: 1,Alice")

    def test_invalid_format_invalid_count(self):
        with pytest.raises(ValueError, match="invalid count"):
            _decode_toon("[abc]{id,name}: 1,Alice")

    def test_invalid_format_missing_brace(self):
        with pytest.raises(ValueError, match="missing opening brace"):
            _decode_toon("[2]id,name}: 1,Alice")

    def test_invalid_format_missing_separator(self):
        with pytest.raises(ValueError, match="missing value separator"):
            _decode_toon("[2]{id,name} 1,Alice")

    def test_toon_count_limit_enforced(self):
        """Test that malicious TOON responses with excessive counts are rejected."""
        malicious = "[1000001]{a}: 1"
        with pytest.raises(ValueError, match="exceeds maximum"):
            _decode_toon(malicious)

    def test_round_trip(self):
        """Test that encoding and decoding are reversible."""
        original = [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False},
            {"id": 3, "name": "Charlie", "active": True},
        ]
        encoded = _encode_toon(original)
        decoded = _decode_toon(encoded)
        assert decoded == original

    def test_round_trip_special_characters(self):
        """Test round-trip with special characters."""
        test_cases = [
            # Commas in values
            [{"id": 1, "name": "Doe, John", "active": True}],
            # Colons in values
            [{"id": 2, "name": "Time: 10:00", "active": False}],
            # Brackets in values
            [{"id": 3, "name": "Array[0]", "active": True}],
            # Newlines and tabs (escaped)
            [{"id": 4, "name": "Line1\nLine2", "active": False}],
            # Mixed special chars
            [{"id": 5, "name": "Hello, [World]: Test", "active": True}],
        ]

        for original in test_cases:
            encoded = _encode_toon(original)
            decoded = _decode_toon(encoded)
            assert decoded == original, f"Failed for: {original}"

    def test_round_trip_null_values(self):
        """Test round-trip with null values."""
        original = [
            {"id": 1, "name": "Alice", "email": None},
            {"id": 2, "name": None, "email": "bob@example.com"},
            {"id": 3, "name": "Charlie", "email": None},
        ]
        encoded = _encode_toon(original)
        decoded = _decode_toon(encoded)
        assert decoded == original

    def test_round_trip_empty_strings(self):
        """Test round-trip with empty strings (uniform array)."""
        original = [
            {"id": 1, "name": "", "active": True},
            {"id": 2, "name": "Bob", "active": True},
            {"id": 3, "name": "", "active": False},
        ]
        encoded = _encode_toon(original)
        decoded = _decode_toon(encoded)
        # Note: TOON format treats empty strings as null (known limitation)
        # Empty string values are decoded as None
        expected = [
            {"id": 1, "name": None, "active": True},
            {"id": 2, "name": "Bob", "active": True},
            {"id": 3, "name": None, "active": False},
        ]
        assert decoded == expected

    def test_round_trip_unicode(self):
        """Test round-trip with Unicode characters (uniform array)."""
        original = [
            {"id": 1, "name": "日本語", "active": True},
            {"id": 2, "name": "Emoji 🎉", "active": False},
            {"id": 3, "name": "Привет", "active": True},
            {"id": 4, "name": "العربية", "active": False},
        ]
        encoded = _encode_toon(original)
        decoded = _decode_toon(encoded)
        assert decoded == original

    def test_round_trip_nested_structures(self):
        """Test round-trip with nested JSON structures in values."""
        original = [
            {"id": 1, "data": '{"nested": "value"}', "active": True},
            {"id": 2, "data": '[1, 2, 3]', "active": False},
            {"id": 3, "data": '{"key": "value, with, commas"}', "active": True},
        ]
        encoded = _encode_toon(original)
        decoded = _decode_toon(encoded)
        assert decoded == original


class TestCompressionRatio:
    """Test compression performance."""

    def test_uniform_array_compression(self):
        """Test that TOON achieves significant compression on uniform arrays."""
        # Simulate a typical database result
        data = [
            {
                "id": i,
                "name": f"User{i}",
                "email": f"user{i}@example.com",
                "created_at": "2026-03-15T10:00:00Z",
                "active": True,
            }
            for i in range(100)
        ]

        json_size = len(json.dumps(data))
        toon_encoded = _encode_toon(data)
        toon_size = len(toon_encoded)

        # TOON should be significantly smaller
        compression_ratio = (1 - toon_size / json_size) * 100

        # Expect at least 40% compression
        assert compression_ratio >= 40, f"Only {compression_ratio:.1f}% compression, expected >= 40%"

    def test_large_keys_compression(self):
        """Test compression with many long key names."""
        data = [
            {
                "user_identifier": str(i),
                "user_display_name": f"User {i}",
                "user_email_address": f"user{i}@example.com",
                "user_profile_url": f"https://example.com/users/{i}",
            }
            for i in range(50)
        ]

        json_size = len(json.dumps(data))
        toon_encoded = _encode_toon(data)
        toon_size = len(toon_encoded)

        compression_ratio = (1 - toon_size / json_size) * 100

        # With long keys, compression should be even better
        assert compression_ratio >= 50, f"Only {compression_ratio:.1f}% compression, expected >= 50%"
