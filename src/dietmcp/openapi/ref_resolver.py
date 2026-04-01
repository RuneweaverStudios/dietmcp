"""OpenAPI schema reference resolution.

Provides custom $ref resolution with caching and better error handling
than the default prance library behavior.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RefResolver:
    """Resolve $ref references in OpenAPI specs.

    Supports local JSON pointers (e.g., "#/components/schemas/User") with
    caching for performance and recursive reference resolution.
    """

    def __init__(self, spec: Dict[str, Any]) -> None:
        """Initialize resolver with spec.

        Args:
            spec: OpenAPI spec dictionary
        """
        self.spec = spec
        self._cache: Dict[str, Any] = {}
        self._resolution_depth: Dict[str, int] = {}

    def resolve(self, ref: str) -> Any:
        """Resolve a $ref reference.

        Args:
            ref: Reference string (e.g., "#/components/schemas/User")

        Returns:
            Resolved object

        Raises:
            ValueError: If reference cannot be resolved or circular reference detected
        """
        if ref in self._cache:
            return self._cache[ref]

        # Track resolution depth to detect circular references
        if ref in self._resolution_depth:
            raise ValueError(f"Circular reference detected: {ref}")

        if not ref.startswith("#/"):
            raise ValueError(
                f"Only local references (starting with #/) are supported: {ref}"
            )

        # Increment depth for this ref
        self._resolution_depth[ref] = self._resolution_depth.get(ref, 0) + 1

        try:
            # Remove "#/" prefix and split by "/"
            parts = ref[2:].split("/")

            # Navigate spec
            current = self.spec
            for part in parts:
                if not isinstance(current, dict):
                    raise ValueError(
                        f"Cannot navigate through non-dict object at reference: {ref}"
                    )
                if part not in current:
                    raise ValueError(f"Reference not found: {ref} (missing '{part}')")
                current = current[part]

            # Handle nested references recursively
            if isinstance(current, dict) and "$ref" in current:
                nested_ref = current["$ref"]
                logger.debug(f"Resolving nested reference: {nested_ref} (from {ref})")
                resolved = self.resolve(nested_ref)
                self._cache[ref] = resolved
                return resolved

            # Cache and return
            self._cache[ref] = current
            return current

        finally:
            # Decrement depth when done
            self._resolution_depth[ref] -= 1
            if self._resolution_depth[ref] == 0:
                del self._resolution_depth[ref]

    def resolve_all(self, obj: Any) -> Any:
        """Recursively resolve all $ref in an object.

        Args:
            obj: Object to resolve (dict, list, or primitive)

        Returns:
            Object with all $ref resolved
        """
        if isinstance(obj, dict):
            result: Dict[str, Any] = {}
            for key, value in obj.items():
                if key == "$ref" and isinstance(value, str):
                    # Found a $ref, resolve it
                    return self.resolve(value)
                elif isinstance(value, (dict, list)):
                    # Recurse into nested structures
                    result[key] = self.resolve_all(value)
                else:
                    # Keep primitive values as-is
                    result[key] = value
            return result
        elif isinstance(obj, list):
            # Process all items in list
            return [self.resolve_all(item) for item in obj]
        else:
            # Return primitive values as-is
            return obj

    def clear_cache(self) -> None:
        """Clear the resolution cache.

        Useful if the spec is modified after initial resolution.
        """
        self._cache.clear()
        self._resolution_depth.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about the resolution cache.

        Returns:
            Dictionary with cache size and resolution count
        """
        return {
            "cache_size": len(self._cache),
            "active_resolutions": len(self._resolution_depth),
        }
