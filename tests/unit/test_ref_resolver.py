"""Unit tests for OpenAPI $ref resolver.

Tests reference resolution, caching, circular reference detection,
and nested reference handling.
"""

from __future__ import annotations

import pytest

from dietmcp.openapi.ref_resolver import RefResolver


class TestRefResolver:
    """Test basic reference resolution."""

    def test_resolve_simple_schema_ref(self):
        """Test resolving a simple schema reference."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/schemas/User")

        assert result == {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"}
            }
        }

    def test_resolve_parameter_ref(self):
        """Test resolving a parameter reference."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "parameters": {
                    "LimitParam": {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer"}
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/parameters/LimitParam")

        assert result["name"] == "limit"
        assert result["in"] == "query"
        assert result["schema"] == {"type": "integer"}

    def test_resolve_response_ref(self):
        """Test resolving a response reference."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "responses": {
                    "NotFound": {
                        "description": "Resource not found",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/responses/NotFound")

        assert result["description"] == "Resource not found"
        assert "content" in result

    def test_resolve_nonexistent_ref(self):
        """Test that resolving a non-existent reference raises ValueError."""
        spec = {
            "openapi": "3.0.0",
            "components": {"schemas": {}}
        }

        resolver = RefResolver(spec)

        with pytest.raises(ValueError, match="Reference not found"):
            resolver.resolve("#/components/schemas/NonExistent")

    def test_resolve_external_ref_not_supported(self):
        """Test that external references are not supported."""
        spec = {"openapi": "3.0.0"}

        resolver = RefResolver(spec)

        with pytest.raises(ValueError, match="Only local references"):
            resolver.resolve("https://example.com/schema.json")


class TestNestedReferences:
    """Test nested and recursive reference resolution."""

    def test_resolve_nested_ref(self):
        """Test that resolve() doesn't recursively resolve nested $refs by default."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "BaseUser": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"}
                        }
                    },
                    "ExtendedUser": {
                        "type": "object",
                        "allOf": [
                            {"$ref": "#/components/schemas/BaseUser"}
                        ],
                        "properties": {
                            "email": {"type": "string"}
                        }
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/schemas/ExtendedUser")

        # resolve() only resolves the direct ref, not nested refs
        assert result["type"] == "object"
        assert "allOf" in result
        # The $ref in allOf is NOT resolved by resolve()
        assert result["allOf"][0] == {"$ref": "#/components/schemas/BaseUser"}

    def test_resolve_all_with_nested_refs(self):
        """Test resolve_all with nested references throughout spec."""
        spec = {
            "openapi": "3.0.0",
            "paths": {
                "/users": {
                    "get": {
                        "parameters": [
                            {"$ref": "#/components/parameters/LimitParam"}
                        ]
                    }
                }
            },
            "components": {
                "parameters": {
                    "LimitParam": {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer"}
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve_all(spec)

        # Parameters should be fully resolved
        assert "parameters" in result["paths"]["/users"]["get"]
        params = result["paths"]["/users"]["get"]["parameters"]
        assert isinstance(params, list)
        assert len(params) == 1
        assert params[0]["name"] == "limit"

    def test_deeply_nested_refs(self):
        """Test resolving multiple levels of nested references."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "Level1": {"type": "string"},
                    "Level2": {"$ref": "#/components/schemas/Level1"},
                    "Level3": {"$ref": "#/components/schemas/Level2"}
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/schemas/Level3")

        # Should resolve all the way to Level1
        assert result == {"type": "string"}


class TestCaching:
    """Test reference resolution caching."""

    def test_cache_hit(self):
        """Test that resolved references are cached."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}}
                    }
                }
            }
        }

        resolver = RefResolver(spec)

        # Resolve twice
        result1 = resolver.resolve("#/components/schemas/User")
        result2 = resolver.resolve("#/components/schemas/User")

        # Should return same object (cached)
        assert result1 is result2

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "User": {"type": "object"},
                    "Product": {"type": "object"}
                }
            }
        }

        resolver = RefResolver(spec)

        # Resolve multiple refs
        resolver.resolve("#/components/schemas/User")
        resolver.resolve("#/components/schemas/Product")
        resolver.resolve("#/components/schemas/User")  # Cache hit

        stats = resolver.get_cache_stats()
        assert stats["cache_size"] == 2  # Two unique refs cached
        assert stats["active_resolutions"] == 0  # No active resolutions

    def test_clear_cache(self):
        """Test clearing the resolution cache."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "User": {"type": "object"}
                }
            }
        }

        resolver = RefResolver(spec)

        # Resolve and verify cache
        resolver.resolve("#/components/schemas/User")
        assert resolver.get_cache_stats()["cache_size"] == 1

        # Clear cache
        resolver.clear_cache()
        assert resolver.get_cache_stats()["cache_size"] == 0


class TestCircularReferences:
    """Test circular reference detection."""

    def test_circular_ref_detection(self):
        """Test that direct circular references are detected."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    # Direct circular ref at top level
                    "CircularRef": {"$ref": "#/components/schemas/CircularRef"}
                }
            }
        }

        resolver = RefResolver(spec)

        with pytest.raises(ValueError, match="Circular reference detected"):
            resolver.resolve("#/components/schemas/CircularRef")

    def test_nested_circular_ref_allowed(self):
        """Test that circular refs nested in properties are allowed (common pattern)."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "Node": {
                        "type": "object",
                        "properties": {
                            "next": {"$ref": "#/components/schemas/Node"}
                        }
                    }
                }
            }
        }

        resolver = RefResolver(spec)

        # This should NOT raise an error because the $ref is nested
        # This is a common pattern in OpenAPI (linked lists, trees)
        result = resolver.resolve("#/components/schemas/Node")
        assert result["type"] == "object"
        assert "properties" in result

    def test_mutual_circular_refs(self):
        """Test detection of mutually circular references."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"$ref": "#/components/schemas/A"}
                }
            }
        }

        resolver = RefResolver(spec)

        with pytest.raises(ValueError, match="Circular reference detected"):
            resolver.resolve("#/components/schemas/A")


class TestResolveAll:
    """Test recursive resolution of all references in spec."""

    def test_resolve_all_primitives(self):
        """Test that primitive values pass through unchanged."""
        resolver = RefResolver({})

        assert resolver.resolve_all("string") == "string"
        assert resolver.resolve_all(123) == 123
        assert resolver.resolve_all(True) is True
        assert resolver.resolve_all(None) is None

    def test_resolve_all_list(self):
        """Test resolving references in lists."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "Item": {"type": "string"}
                }
            }
        }

        resolver = RefResolver(spec)
        input_list = [
            "plain",
            {"$ref": "#/components/schemas/Item"},
            {"nested": "value"}
        ]

        result = resolver.resolve_all(input_list)

        assert result[0] == "plain"
        assert result[1] == {"type": "string"}
        assert result[2] == {"nested": "value"}

    def test_resolve_all_dict(self):
        """Test resolving references in dictionaries."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "Config": {"type": "object"}
                }
            }
        }

        resolver = RefResolver(spec)
        input_dict = {
            "field1": "value",
            "field2": {"$ref": "#/components/schemas/Config"},
            "nested": {
                "item": {"$ref": "#/components/schemas/Config"}
            }
        }

        result = resolver.resolve_all(input_dict)

        assert result["field1"] == "value"
        assert result["field2"] == {"type": "object"}
        assert result["nested"]["item"] == {"type": "object"}

    def test_resolve_all_preserves_non_ref_dicts(self):
        """Test that non-$ref dictionaries are preserved."""
        spec = {"openapi": "3.0.0"}
        resolver = RefResolver(spec)

        input_dict = {
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"}
                }
            }
        }

        result = resolver.resolve_all(input_dict)

        assert result == input_dict

    def test_resolve_all_empty_structures(self):
        """Test resolving empty lists and dicts."""
        resolver = RefResolver({})

        assert resolver.resolve_all([]) == []
        assert resolver.resolve_all({}) == {}


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_ref_with_special_characters(self):
        """Test references with special characters in path."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "User-Profile": {
                        "type": "object"
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/schemas/User-Profile")

        assert result["type"] == "object"

    def test_ref_to_non_dict_value(self):
        """Test reference to a non-dictionary value."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "Value": "string"
                }
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/schemas/Value")

        assert result == "string"

    def test_empty_spec(self):
        """Test resolver with minimal spec."""
        spec = {"openapi": "3.0.0"}
        resolver = RefResolver(spec)

        # Should not error, just have empty cache
        stats = resolver.get_cache_stats()
        assert stats["cache_size"] == 0

    def test_ref_at_root_level(self):
        """Test reference to root-level properties."""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0"
            }
        }

        resolver = RefResolver(spec)
        result = resolver.resolve("#/info/title")

        assert result == "Test API"

    def test_ref_navigates_through_multiple_levels(self):
        """Test reference that navigates through multiple levels."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "object",
                                "properties": {
                                    "street": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            }
        }

        # Note: This is testing that we can navigate to nested properties
        # In real OpenAPI, refs point to components, not nested properties
        resolver = RefResolver(spec)
        result = resolver.resolve("#/components/schemas/User/properties/address")

        assert result["type"] == "object"
        assert "properties" in result


class TestIntegrationScenarios:
    """Test realistic OpenAPI scenarios."""

    def test_complete_api_spec_resolution(self):
        """Test resolving references in a complete API spec."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "getUsers",
                        "parameters": [
                            {"$ref": "#/components/parameters/PageParam"}
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/UserList"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "parameters": {
                    "PageParam": {
                        "name": "page",
                        "in": "query",
                        "schema": {"type": "integer"}
                    }
                },
                "schemas": {
                    "UserList": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/User"}
                    },
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }

        resolver = RefResolver(spec)
        resolved = resolver.resolve_all(spec)

        # Verify parameters resolved
        params = resolved["paths"]["/users"]["get"]["parameters"]
        assert isinstance(params, list)
        assert params[0]["name"] == "page"

        # Verify response schema resolved
        response_schema = resolved["paths"]["/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert response_schema["type"] == "array"
        # Items should be resolved (not a $ref)
        assert "items" in response_schema

    def test_reusable_components(self):
        """Test that resolve() caches component references."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "Timestamp": {
                        "type": "string",
                        "format": "date-time"
                    },
                    "CreatedEntity": {
                        "type": "object",
                        "properties": {
                            "createdAt": {"$ref": "#/components/schemas/Timestamp"}
                        }
                    },
                    "UpdatedEntity": {
                        "type": "object",
                        "properties": {
                            "updatedAt": {"$ref": "#/components/schemas/Timestamp"}
                        }
                    }
                }
            }
        }

        resolver = RefResolver(spec)

        # Both should resolve and be cached
        created = resolver.resolve("#/components/schemas/CreatedEntity")
        updated = resolver.resolve("#/components/schemas/UpdatedEntity")

        # The schemas are resolved (but nested $refs in properties are not)
        assert created["type"] == "object"
        assert updated["type"] == "object"
        # The $ref in properties is preserved by resolve()
        assert created["properties"]["createdAt"] == {"$ref": "#/components/schemas/Timestamp"}
        assert updated["properties"]["updatedAt"] == {"$ref": "#/components/schemas/Timestamp"}
