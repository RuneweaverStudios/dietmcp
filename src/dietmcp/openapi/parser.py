"""OpenAPI specification parser.

Parses OpenAPI 3.0.x specifications from URLs, file paths, or dictionaries.
Resolves $ref references and extracts endpoints, parameters, and schemas.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import prance
import yaml

from dietmcp.models.openapi import OpenAPIEndpoint, OpenAPIParameter, OpenAPISpec, SecurityScheme
from dietmcp.openapi.ref_resolver import RefResolver
from dietmcp.openapi.response_schema import extract_response_schema
from dietmcp.security.url_validator import validate_url


class OpenAPIParserError(Exception):
    """Exception raised when parsing fails."""

    pass


class OpenAPIParser:
    """Parser for OpenAPI 3.0.x specifications."""

    def parse_spec(self, source: str | dict | Path) -> OpenAPISpec:
        """Parse OpenAPI spec from URL, file path, or dict.

        Args:
            source: URL (http/https), file path, or dict containing parsed spec

        Returns:
            OpenAPISpec object with all endpoints and metadata

        Raises:
            OpenAPIParserError: If spec is invalid or cannot be parsed
        """
        try:
            # Load spec based on source type
            if isinstance(source, dict):
                raw_spec = source
            elif isinstance(source, Path):
                raw_spec = self._load_from_file(source)
            elif isinstance(source, str):
                if self._is_url(source):
                    raw_spec = self._load_from_url(source)
                else:
                    raw_spec = self._load_from_file(Path(source))
            else:
                raise OpenAPIParserError(
                    f"Unsupported source type: {type(source)}"
                )

            # Resolve $ref references using prance
            resolved_spec = self._resolve_references(raw_spec)

            # Validate OpenAPI version
            self._validate_version(resolved_spec)

            # Extract spec metadata
            info = resolved_spec.get("openapi", resolved_spec.get("swagger", ""))
            title = resolved_spec.get("info", {}).get("title", "Unknown API")
            version = resolved_spec.get("info", {}).get("version", "1.0.0")
            description = resolved_spec.get("info", {}).get("description")

            # Extract servers
            servers = resolved_spec.get("servers", [])
            if not servers and isinstance(source, str) and self._is_url(source):
                # Fallback to URL if no servers defined
                servers = [{"url": urlparse(source).scheme + "://" + urlparse(source).netloc}]

            # Extract security schemes
            security_schemes = {}
            security_schemes_list = []
            components = resolved_spec.get("components", {})
            if "securitySchemes" in components:
                security_schemes = components["securitySchemes"]
                # Parse into structured SecurityScheme models
                for name, scheme_dict in security_schemes.items():
                    scheme = SecurityScheme(
                        name=name,
                        type=scheme_dict.get("type", ""),
                        description=scheme_dict.get("description"),
                        in_=scheme_dict.get("in"),
                        scheme=scheme_dict.get("scheme"),
                        bearer_format=scheme_dict.get("bearerFormat"),
                        flows=scheme_dict.get("flows"),
                        scopes=scheme_dict.get("scopes"),
                        open_id_connect_url=scheme_dict.get("openIdConnectUrl"),
                    )
                    security_schemes_list.append(scheme)

            # Extract component schemas
            components_schemas = components.get("schemas", {})

            # Extract all endpoints
            endpoints = self._extract_endpoints(resolved_spec)

            return OpenAPISpec(
                title=title,
                version=version,
                description=description,
                servers=servers,
                endpoints=endpoints,
                security_schemes=security_schemes,
                security_schemes_list=security_schemes_list,
                components_schemas=components_schemas,
                raw_spec=resolved_spec,
            )

        except Exception as e:
            raise OpenAPIParserError(f"Failed to resolve references: {e}") from e
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise OpenAPIParserError(f"Failed to parse spec file: {e}") from e
        except FileNotFoundError as e:
            raise OpenAPIParserError(f"Spec file not found: {e}") from e
        except Exception as e:
            raise OpenAPIParserError(f"Unexpected error parsing spec: {e}") from e

    def extract_endpoints(self, spec: OpenAPISpec) -> list[OpenAPIEndpoint]:
        """Extract all endpoints from a parsed spec (deprecated: use parse_spec).

        Args:
            spec: Parsed OpenAPI spec

        Returns:
            List of OpenAPIEndpoint objects
        """
        return spec.endpoints

    def _is_url(self, source: str) -> bool:
        """Check if source is a URL."""
        try:
            result = urlparse(source)
            return result.scheme in ["http", "https"]
        except Exception:
            return False

    def _load_from_file(self, path: Path) -> dict[str, Any]:
        """Load OpenAPI spec from a local file (JSON or YAML).

        Args:
            path: Path to the spec file

        Returns:
            Parsed spec as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            OpenAPIParserError: If path is outside allowed directories or file cannot be parsed
        """
        # Resolve to absolute path
        resolved_path = path.resolve()

        # Define allowed base directories
        allowed_dirs = [
            Path.home() / ".config" / "dietmcp" / "specs",
            Path.cwd() / "specs",
            Path.cwd() / ".specs",
        ]

        # Check if path is within allowed directories
        is_allowed = any(
            str(resolved_path).startswith(str(d.resolve()))
            for d in allowed_dirs
            if d.exists()
        )

        if not is_allowed:
            raise OpenAPIParserError(
                f"Spec file path outside allowed directories: {resolved_path}\n"
                f"Allowed: {[str(d) for d in allowed_dirs if d.exists()]}"
            )

        # Check for symlinks pointing outside allowed dirs
        if resolved_path.is_symlink():
            target = resolved_path.resolve()
            is_target_allowed = any(
                str(target).startswith(str(d.resolve()))
                for d in allowed_dirs
                if d.exists()
            )
            if not is_target_allowed:
                raise OpenAPIParserError(
                    f"Symlink target outside allowed directories: {target}"
                )

        if not resolved_path.exists():
            raise FileNotFoundError(f"Spec file not found: {resolved_path}")

        # Read with secure permissions
        content = resolved_path.read_text()

        # Try JSON first, then YAML
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise OpenAPIParserError(f"Failed to parse file as JSON or YAML: {e}")

    def _load_from_url(self, url: str) -> dict[str, Any]:
        """Load OpenAPI spec from a URL.

        Args:
            url: URL to the spec

        Returns:
            Parsed spec as dictionary

        Raises:
            OpenAPIParserError: If URL is invalid or spec cannot be loaded
        """
        # Validate URL before fetching (SSRF protection)
        if not self._is_url(url):
            raise OpenAPIParserError(f"Invalid URL: {url}")

        # Validate URL is not internal/private (SSRF protection)
        try:
            validate_url(url)
        except ValueError as e:
            raise OpenAPIParserError(f"URL validation failed: {e}") from e

        # Use prance to load from URL (handles JSON/YAML detection)
        try:
            parser = prance.ResolvingParser(url, backend="openapi-spec-validator")
            parser.parse()
            return parser.specification
        except Exception as e:
            raise OpenAPIParserError(f"Failed to load spec from URL: {e}")

    def _resolve_references(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Resolve all $ref references in the spec.

        Uses custom RefResolver for better error handling and caching.
        Prance is still used for initial validation and external reference handling.

        Args:
            spec: Unresolved spec dictionary

        Returns:
            Resolved spec dictionary

        Raises:
            OpenAPIParserError: If reference resolution fails
        """
        # First, use prance for validation and external references
        import tempfile
        import shutil

        # Create secure temp directory
        temp_dir = Path(tempfile.mkdtemp())
        temp_dir.chmod(0o700)

        temp_path = temp_dir / f"spec_{os.getpid()}_{id(spec)}.json"

        try:
            # Write spec with restricted permissions
            spec_json = json.dumps(spec)
            temp_path.write_text(spec_json, encoding="utf-8")
            temp_path.chmod(0o600)

            # Use prance for validation
            parser = prance.ResolvingParser(
                str(temp_path), backend="openapi-spec-validator"
            )
            parser.parse()
            validated_spec = parser.specification

            # Now use custom RefResolver for better $ref resolution with caching
            resolver = RefResolver(validated_spec)
            resolved_spec = resolver.resolve_all(validated_spec)

            # Log cache stats for debugging
            cache_stats = resolver.get_cache_stats()
            if cache_stats["cache_size"] > 0:
                logger = __import__("logging").getLogger(__name__)
                logger.debug(
                    f"Reference resolution complete: "
                    f"{cache_stats['cache_size']} references cached"
                )

            return resolved_spec

        except Exception as e:
            raise OpenAPIParserError(f"Failed to resolve references: {e}") from e
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _validate_version(self, spec: dict[str, Any]) -> None:
        """Validate that spec is OpenAPI 3.0.x.

        Args:
            spec: Parsed spec dictionary

        Raises:
            OpenAPIParserError: If version is not supported
        """
        openapi_version = spec.get("openapi")
        if not openapi_version:
            raise OpenAPIParserError(
                "Missing 'openapi' version field. Is this a valid OpenAPI 3.x spec?"
            )

        # Parse major version
        major_version = openapi_version.split(".")[0]
        if major_version != "3":
            raise OpenAPIParserError(
                f"Unsupported OpenAPI version: {openapi_version}. "
                f"Only OpenAPI 3.x is supported."
            )

    def _extract_endpoints(self, spec: dict[str, Any]) -> list[OpenAPIEndpoint]:
        """Extract all endpoints from the spec.

        Args:
            spec: Resolved OpenAPI spec dictionary

        Returns:
            List of OpenAPIEndpoint objects
        """
        endpoints = []
        paths = spec.get("paths", {})

        for path, path_item in paths.items():
            # Extract path-level parameters (apply to all methods)
            path_params = path_item.get("parameters", [])

            # Extract each HTTP method
            for method, operation in path_item.items():
                if method.lower() not in [
                    "get",
                    "post",
                    "put",
                    "delete",
                    "patch",
                    "options",
                    "head",
                    "trace",
                ]:
                    continue

                # Merge path-level and operation-level parameters
                operation_params = operation.get("parameters", [])
                all_params = self._parse_parameters(path_params + operation_params)

                # Group parameters by location
                path_param_list = [p for p in all_params if p.in_ == "path"]
                query_param_list = [p for p in all_params if p.in_ == "query"]
                header_param_list = [p for p in all_params if p.in_ == "header"]
                cookie_param_list = [p for p in all_params if p.in_ == "cookie"]

                # Extract responses
                responses = operation.get("responses", {})
                success_schema = None
                error_schema = None

                # Find 2xx success response
                for status, response in responses.items():
                    if status.startswith("2"):
                        # Use response_schema module for better extraction
                        try:
                            from dietmcp.openapi.response_schema import ResponseSchema
                            schema_info = extract_response_schema(response, "application/json")
                            success_schema = schema_info.schema
                        except Exception:
                            # Fallback to manual extraction
                            if "$ref" in response:
                                ref = response["$ref"]
                                if ref.startswith("#/components/schemas/"):
                                    schema_name = ref.split("/")[-1]
                                    success_schema = {"$ref": schema_name}
                            elif "content" in response:
                                for content_type, content in response["content"].items():
                                    if "schema" in content:
                                        success_schema = content["schema"]
                                        break
                        break
                    elif status.startswith(("4", "5")):
                        # Extract error schema (first one found)
                        if error_schema is None:
                            try:
                                schema_info = extract_response_schema(response, "application/json")
                                error_schema = schema_info.schema
                            except Exception:
                                if "content" in response:
                                    for content_type, content in response["content"].items():
                                        if "schema" in content:
                                            error_schema = content["schema"]
                                            break

                endpoint = OpenAPIEndpoint(
                    path=path,
                    method=method.upper(),
                    operation_id=operation.get("operationId"),
                    summary=operation.get("summary"),
                    description=operation.get("description"),
                    parameters=all_params,
                    request_body=operation.get("requestBody"),
                    responses=responses,
                    success_schema=success_schema,
                    error_schema=error_schema,
                    tags=operation.get("tags", []),
                    security=operation.get("security", []),
                    path_params=path_param_list,
                    query_params=query_param_list,
                    header_params=header_param_list,
                    cookie_params=cookie_param_list,
                )

                endpoints.append(endpoint)

        return endpoints

    def _parse_parameters(self, params: list[dict]) -> list[OpenAPIParameter]:
        """Parse parameter definitions.

        Args:
            params: List of parameter dictionaries from spec

        Returns:
            List of OpenAPIParameter objects
        """
        parsed = []

        for param in params:
            # Handle $ref (should already be resolved, but check anyway)
            if "$ref" in param:
                continue

            parsed_param = OpenAPIParameter(
                name=param.get("name", ""),
                in_=param.get("in", "query"),
                description=param.get("description"),
                required=param.get("required", False),
                schema_=param.get("schema"),
                example=param.get("example"),
                style=param.get("style"),
                explode=param.get("explode"),
                deprecated=param.get("deprecated", False),
                allow_empty_value=param.get("allowEmptyValue", False),
            )
            parsed.append(parsed_param)

        return parsed
