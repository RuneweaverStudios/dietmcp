# OpenAPI $ref Reference Resolution Implementation

## Overview

Implemented a custom `RefResolver` class for OpenAPI schema reference resolution with better error handling and caching than the default prance library behavior.

## Files Created

### `/Users/ghost/Desktop/dietmcp/src/dietmcp/openapi/ref_resolver.py`

New module providing custom $ref resolution with:
- **Local JSON Pointer support**: Resolves references like `#/components/schemas/User`
- **Caching**: Stores resolved references for performance
- **Circular reference detection**: Prevents infinite loops
- **Recursive resolution**: `resolve_all()` method for full spec resolution
- **Better error messages**: Clear indication of what failed and why

## Key Features

### 1. Reference Resolution

```python
resolver = RefResolver(spec)
schema = resolver.resolve("#/components/schemas/User")
```

- Navigates the spec using JSON pointer syntax
- Returns the resolved object
- Caches results for subsequent lookups

### 2. Recursive Resolution

```python
resolver = RefResolver(spec)
fully_resolved = resolver.resolve_all(spec)
```

- Recursively resolves all $ref in the spec
- Handles nested structures (dicts, lists)
- Preserves non-reference data

### 3. Caching

```python
stats = resolver.get_cache_stats()
# Returns: {"cache_size": N, "active_resolutions": M}

resolver.clear_cache()  # Clear when needed
```

### 4. Circular Reference Detection

Detects direct circular references:
```python
# This will raise ValueError
spec = {
    "components": {
        "schemas": {
            "Circular": {"$ref": "#/components/schemas/Circular"}
        }
    }
}
```

Allows nested circular refs (common pattern):
```python
# This is OK - common in linked lists, trees
spec = {
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
```

## Integration with Parser

Modified `/Users/ghost/Desktop/dietmcp/src/dietmcp/openapi/parser.py`:

1. **Import**: Added `RefResolver` import
2. **Enhanced `_resolve_references()`**: 
   - Still uses prance for initial validation
   - Applies custom RefResolver for better $ref handling
   - Logs cache statistics for debugging

```python
def _resolve_references(self, spec: dict[str, Any]) -> dict[str, Any]:
    # Use prance for validation
    parser = prance.ResolvingParser(...)
    validated_spec = parser.specification
    
    # Use custom RefResolver for better resolution
    resolver = RefResolver(validated_spec)
    resolved_spec = resolver.resolve_all(validated_spec)
    
    return resolved_spec
```

## Testing

Created comprehensive test suite in `/Users/ghost/Desktop/dietmcp/tests/unit/test_ref_resolver.py`:

- **26 tests** covering:
  - Basic reference resolution
  - Nested references
  - Circular reference detection
  - Caching behavior
  - Edge cases and error conditions
  - Integration scenarios
  - Complete API spec resolution

### Test Results

```
tests/unit/test_ref_resolver.py::26 PASSED
tests/unit/test_openapi_parser.py::63 PASSED
Total: 89 tests passed
```

## Benefits

1. **Better Error Handling**: Clear error messages indicate exactly what failed
2. **Performance**: Caching avoids redundant resolution work
3. **Maintainability**: Custom code is easier to debug than prance internals
4. **Flexibility**: Can extend with additional features (external refs, etc.)
5. **Safety**: Circular reference detection prevents infinite loops

## Usage Example

```python
from dietmcp.openapi.parser import OpenAPIParser

parser = OpenAPIParser()
spec = parser.parse_spec("openapi.json")

# All $ref references are now resolved with:
# - Better error messages
# - Cached resolution
# - Circular reference protection
```

## Future Enhancements

Potential improvements:
1. Support for external references (URLs, file paths)
2. Reference resolution depth limits
3. More detailed cache statistics
4. Support for $ref in additional contexts
5. Custom resolution strategies for different spec patterns
