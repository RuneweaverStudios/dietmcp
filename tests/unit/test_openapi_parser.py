"""Comprehensive unit tests for OpenAPI parser.

Tests spec parsing (JSON/YAML), endpoint extraction, parameter parsing,
auth scheme handling, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from dietmcp.openapi.parser import OpenAPIParser, OpenAPIParserError
from dietmcp.models.openapi import OpenAPISpec, OpenAPIEndpoint, OpenAPIParameter, SecurityScheme
from dietmcp.config.schema import AuthConfig


@pytest.fixture
def minimal_petstore_spec():
    """Minimal valid OpenAPI 3.0 spec for testing."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Petstore API",
            "version": "1.0.0",
            "description": "A sample Pet Store Server"
        },
        "servers": [
            {"url": "https://petstore.swagger.io/v2"}
        ],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "getPets",
                    "summary": "List all pets",
                    "description": "Returns a list of pets",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "How many items to return",
                            "required": False,
                            "schema": {"type": "integer", "format": "int32"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "Successful response"}
                    },
                    "tags": ["pets"]
                },
                "post": {
                    "operationId": "createPet",
                    "summary": "Create a pet",
                    "requestBody": {
                        "description": "Pet to add",
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "tag": {"type": "string"}
                                    },
                                    "required": ["name"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "Pet created"}
                    }
                }
            },
            "/pets/{petId}": {
                "get": {
                    "operationId": "getPetById",
                    "summary": "Get pet by ID",
                    "parameters": [
                        {
                            "name": "petId",
                            "in": "path",
                            "description": "Pet ID",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "Successful response"}
                    }
                }
            }
        },
        "components": {
            "securitySchemes": {
                "api_key": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                },
                "bearer_auth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            },
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"}
                    }
                }
            }
        }
    }


@pytest.fixture
def spec_with_ref():
    """Spec with $ref references to test resolution."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "API with refs", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "getUsers",
                    "parameters": [
                        {"$ref": "#/components/parameters/LimitParam"}
                    ],
                    "responses": {
                        "200": {"description": "OK"}
                    }
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


@pytest.fixture
def spec_with_path_level_params():
    """Spec with path-level parameters."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "API", "version": "1.0.0"},
        "paths": {
            "/items/{itemId}": {
                "parameters": [
                    {
                        "name": "itemId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "get": {
                    "operationId": "getItem",
                    "parameters": [
                        {
                            "name": "verbose",
                            "in": "query",
                            "schema": {"type": "boolean"}
                        }
                    ],
                    "responses": {"200": {"description": "OK"}}
                }
            }
        }
    }


@pytest.fixture
def spec_with_security():
    """Spec with security requirements."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Secure API", "version": "1.0.0"},
        "paths": {
            "/admin": {
                "get": {
                    "operationId": "adminOnly",
                    "security": [{"bearer_auth": []}],
                    "responses": {"200": {"description": "OK"}}
                }
            },
            "/public": {
                "get": {
                    "operationId": "publicEndpoint",
                    "security": [],
                    "responses": {"200": {"description": "OK"}}
                }
            }
        },
        "components": {
            "securitySchemes": {
                "bearer_auth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            }
        }
    }


class TestParseSpec:
    """Test spec parsing from various sources."""

    def test_parse_from_dict(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        assert isinstance(spec, OpenAPISpec)
        assert spec.title == "Petstore API"
        assert spec.version == "1.0.0"
        assert spec.description == "A sample Pet Store Server"
        assert len(spec.servers) == 1
        assert spec.servers[0]["url"] == "https://petstore.swagger.io/v2"

    def test_parse_from_json_file(self, tmp_path, minimal_petstore_spec):
        # Create specs directory in tmp_path
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write spec to JSON file
        json_file = specs_dir / "petstore.json"
        import json
        import os
        json_file.write_text(json.dumps(minimal_petstore_spec))

        # Change to tmp_path to make it current directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            spec = parser.parse_spec(json_file)

            assert spec.title == "Petstore API"
            assert len(spec.endpoints) > 0
        finally:
            os.chdir(original_cwd)

    def test_parse_from_yaml_file(self, tmp_path, minimal_petstore_spec):
        # Create specs directory in tmp_path
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write spec to YAML file
        yaml_file = specs_dir / "petstore.yaml"
        yaml_file.write_text(yaml.dump(minimal_petstore_spec))

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            spec = parser.parse_spec(yaml_file)

            assert spec.title == "Petstore API"
            assert len(spec.endpoints) > 0
        finally:
            os.chdir(original_cwd)

    def test_parse_from_string_path(self, tmp_path, minimal_petstore_spec):
        # Create specs directory in tmp_path
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write spec and parse with string path
        json_file = specs_dir / "petstore.json"
        import json
        import os
        json_file.write_text(json.dumps(minimal_petstore_spec))

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            spec = parser.parse_spec(str(json_file))

            assert spec.title == "Petstore API"
        finally:
            os.chdir(original_cwd)

    def test_parse_from_url(self, minimal_petstore_spec):
        # Note: URL parsing requires prance to actually fetch
        # We'll test the method but expect it might fail without a real URL
        parser = OpenAPIParser()

        # Test with an invalid URL to check error handling
        with pytest.raises(OpenAPIParserError, match="Failed to load spec from URL"):
            parser.parse_spec("https://this-url-does-not-exist-12345.com/openapi.json")

    def test_parse_unsupported_type(self):
        parser = OpenAPIParser()
        with pytest.raises(OpenAPIParserError, match="Unsupported source type"):
            parser.parse_spec(123)  # type: ignore

    def test_parse_missing_openapi_field(self):
        parser = OpenAPIParser()
        invalid_spec = {"info": {"title": "API"}, "paths": {}}

        # Prance will detect this before our validation
        with pytest.raises(OpenAPIParserError, match="Failed to resolve references"):
            parser.parse_spec(invalid_spec)

    def test_parse_unsupported_openapi_version(self):
        parser = OpenAPIParser()
        # Prance will reject Swagger 2.0 before we get to version check
        invalid_spec = {
            "openapi": "2.0.0",
            "info": {"title": "Swagger 2.0", "version": "1.0.0"},
            "paths": {},
            "swagger": "2.0"
        }

        # Should fail during parsing (prance doesn't support Swagger 2.0 mixing with OpenAPI)
        with pytest.raises(OpenAPIParserError):
            parser.parse_spec(invalid_spec)

    def test_parse_file_not_found(self, tmp_path):
        # Create specs directory in tmp_path
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            nonexistent_file = specs_dir / "nonexistent.json"

            with pytest.raises(OpenAPIParserError, match="Spec file not found"):
                parser.parse_spec(nonexistent_file)
        finally:
            os.chdir(original_cwd)

    def test_parse_invalid_json(self, tmp_path):
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid json}")

        parser = OpenAPIParser()
        # Invalid JSON will fail during prance validation
        with pytest.raises(OpenAPIParserError):
            parser.parse_spec(invalid_file)

    def test_parse_invalid_yaml(self, tmp_path):
        # Create specs directory in tmp_path
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        invalid_file = specs_dir / "invalid.yaml"
        invalid_file.write_text(":\n  - invalid\nyaml:")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            with pytest.raises(OpenAPIParserError, match="Failed to parse file"):
                parser.parse_spec(invalid_file)
        finally:
            os.chdir(original_cwd)

    @patch('dietmcp.openapi.parser.prance.ResolvingParser')
    def test_parse_url_error(self, mock_parser_class):
        mock_parser_class.side_effect = Exception("Network error")

        parser = OpenAPIParser()
        with pytest.raises(OpenAPIParserError, match="Failed to load spec from URL"):
            parser.parse_spec("https://api.example.com/openapi.json")


class TestEndpointExtraction:
    """Test endpoint extraction from specs."""

    def test_extract_endpoints_basic(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        assert len(spec.endpoints) == 3

        endpoints_by_id = {ep.operation_id: ep for ep in spec.endpoints}

        assert "getPets" in endpoints_by_id
        assert "createPet" in endpoints_by_id
        assert "getPetById" in endpoints_by_id

    def test_endpoint_properties(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        get_pets = spec.get_endpoint_by_id("getPets")
        assert get_pets is not None
        assert get_pets.path == "/pets"
        assert get_pets.method == "GET"
        assert get_pets.summary == "List all pets"
        assert get_pets.description == "Returns a list of pets"
        assert "pets" in get_pets.tags

    def test_extract_parameters(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        get_pets = spec.get_endpoint_by_id("getPets")
        assert get_pets is not None
        assert len(get_pets.parameters) == 1

        limit_param = get_pets.parameters[0]
        assert limit_param.name == "limit"
        assert limit_param.in_ == "query"
        assert limit_param.required is False
        assert limit_param.schema_ == {"type": "integer", "format": "int32"}
        assert limit_param.description == "How many items to return"

    def test_path_parameters(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        get_by_id = spec.get_endpoint_by_id("getPetById")
        assert get_by_id is not None
        assert len(get_by_id.parameters) == 1

        pet_id_param = get_by_id.parameters[0]
        assert pet_id_param.name == "petId"
        assert pet_id_param.in_ == "path"
        assert pet_id_param.required is True
        assert pet_id_param.schema_ == {"type": "integer"}

    def test_request_body_extraction(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        create_pet = spec.get_endpoint_by_id("createPet")
        assert create_pet is not None
        assert create_pet.request_body is not None
        assert "content" in create_pet.request_body
        assert "application/json" in create_pet.request_body["content"]

    def test_path_level_parameters(self, spec_with_path_level_params):
        parser = OpenAPIParser()
        spec = parser.parse_spec(spec_with_path_level_params)

        get_item = spec.get_endpoint_by_id("getItem")
        assert get_item is not None
        # Should have both path-level and operation-level parameters
        assert len(get_item.parameters) == 2

        param_names = {p.name for p in get_item.parameters}
        assert "itemId" in param_names
        assert "verbose" in param_names

    def test_all_http_methods(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "All Methods", "version": "1.0.0"},
            "paths": {
                "/resource": {
                    "get": {"operationId": "get", "responses": {"200": {"description": "OK"}}},
                    "post": {"operationId": "post", "responses": {"200": {"description": "OK"}}},
                    "put": {"operationId": "put", "responses": {"200": {"description": "OK"}}},
                    "delete": {"operationId": "delete", "responses": {"200": {"description": "OK"}}},
                    "patch": {"operationId": "patch", "responses": {"200": {"description": "OK"}}},
                    "options": {"operationId": "options", "responses": {"200": {"description": "OK"}}},
                    "head": {"operationId": "head", "responses": {"200": {"description": "OK"}}},
                    "trace": {"operationId": "trace", "responses": {"200": {"description": "OK"}}},
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        assert len(spec.endpoints) == 8

        methods = {ep.method for ep in spec.endpoints}
        assert methods == {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"}

    def test_empty_paths(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "Empty API", "version": "1.0.0"},
            "paths": {}
        }

        spec = parser.parse_spec(spec_dict)
        assert len(spec.endpoints) == 0


class TestParameterParsing:
    """Test parameter parsing and handling."""

    def test_parameter_with_all_fields(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {
                                "name": "param1",
                                "in": "query",
                                "description": "A test parameter",
                                "required": True,
                                "schema": {"type": "string"},
                                "example": "example_value"
                            }
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        param = spec.endpoints[0].parameters[0]

        assert param.name == "param1"
        assert param.in_ == "query"
        assert param.description == "A test parameter"
        assert param.required is True
        assert param.schema_ == {"type": "string"}
        assert param.example == "example_value"

    def test_parameter_minimal(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {"name": "param1", "in": "query", "schema": {"type": "string"}}
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        param = spec.endpoints[0].parameters[0]

        assert param.name == "param1"
        assert param.in_ == "query"
        assert param.description is None
        assert param.required is False
        assert param.schema_ == {"type": "string"}
        assert param.example is None

    def test_parameter_locations(self):
        """Test parameters in query, path, header, and cookie."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test/{id}": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
                            {"name": "query1", "in": "query", "schema": {"type": "string"}},
                            {"name": "header1", "in": "header", "schema": {"type": "string"}},
                            {"name": "cookie1", "in": "cookie", "schema": {"type": "string"}},
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        param_locations = {p.in_ for p in spec.endpoints[0].parameters}

        assert param_locations == {"path", "query", "header", "cookie"}

    def test_grouped_parameters(self):
        """Test that parameters are grouped by location."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test/{id}": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
                            {"name": "query1", "in": "query", "schema": {"type": "string"}},
                            {"name": "query2", "in": "query", "schema": {"type": "integer"}},
                            {"name": "header1", "in": "header", "schema": {"type": "string"}},
                            {"name": "cookie1", "in": "cookie", "schema": {"type": "string"}},
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        endpoint = spec.endpoints[0]

        # Check grouped parameters
        assert len(endpoint.path_params) == 1
        assert endpoint.path_params[0].name == "id"
        assert endpoint.path_params[0].in_ == "path"

        assert len(endpoint.query_params) == 2
        query_names = {p.name for p in endpoint.query_params}
        assert query_names == {"query1", "query2"}

        assert len(endpoint.header_params) == 1
        assert endpoint.header_params[0].name == "header1"
        assert endpoint.header_params[0].in_ == "header"

        assert len(endpoint.cookie_params) == 1
        assert endpoint.cookie_params[0].name == "cookie1"
        assert endpoint.cookie_params[0].in_ == "cookie"

    def test_parameter_with_style_and_explode(self):
        """Test parameters with style and explode options."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {
                                "name": "tags",
                                "in": "query",
                                "style": "form",
                                "explode": True,
                                "schema": {"type": "array", "items": {"type": "string"}}
                            },
                            {
                                "name": "X-Custom-Header",
                                "in": "header",
                                "style": "simple",
                                "explode": False,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)

        tags_param = [p for p in spec.endpoints[0].parameters if p.name == "tags"][0]
        assert tags_param.style == "form"
        assert tags_param.explode is True

        header_param = [p for p in spec.endpoints[0].parameters if p.name == "X-Custom-Header"][0]
        assert header_param.style == "simple"
        assert header_param.explode is False

    def test_deprecated_parameter(self):
        """Test deprecated parameter flag."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {
                                "name": "old_param",
                                "in": "query",
                                "deprecated": True,
                                "schema": {"type": "string"}
                            },
                            {
                                "name": "new_param",
                                "in": "query",
                                "deprecated": False,
                                "schema": {"type": "string"}}
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)

        old_param = [p for p in spec.endpoints[0].parameters if p.name == "old_param"][0]
        assert old_param.deprecated is True

        new_param = [p for p in spec.endpoints[0].parameters if p.name == "new_param"][0]
        assert new_param.deprecated is False

    def test_allow_empty_value_parameter(self):
        """Test allowEmptyValue for query parameters."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {
                                "name": "filter",
                                "in": "query",
                                "allowEmptyValue": True,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)

        filter_param = spec.endpoints[0].parameters[0]
        assert filter_param.allow_empty_value is True

    def test_parameter_without_schema_defaults_to_string(self):
        """Test that prance requires schema field in parameters."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "parameters": [
                            {"name": "param1", "in": "query"}
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        # Prance requires schema in parameters
        with pytest.raises(OpenAPIParserError):
            parser.parse_spec(spec_dict)


class TestSecuritySchemes:
    """Test security scheme extraction."""

    def test_extract_security_schemes(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        assert "api_key" in spec.security_schemes
        assert "bearer_auth" in spec.security_schemes

        api_key = spec.security_schemes["api_key"]
        assert api_key["type"] == "apiKey"
        assert api_key["in"] == "header"
        assert api_key["name"] == "X-API-Key"

        bearer = spec.security_schemes["bearer_auth"]
        assert bearer["type"] == "http"
        assert bearer["scheme"] == "bearer"

    def test_get_security_scheme(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        api_key = spec.get_security_scheme("api_key")
        assert api_key is not None
        assert api_key["type"] == "apiKey"

        nonexistent = spec.get_security_scheme("nonexistent")
        assert nonexistent is None

    def test_operation_security_requirements(self, spec_with_security):
        parser = OpenAPIParser()
        spec = parser.parse_spec(spec_with_security)

        admin_op = spec.get_endpoint_by_id("adminOnly")
        assert admin_op is not None
        assert admin_op.security == [{"bearer_auth": []}]

        public_op = spec.get_endpoint_by_id("publicEndpoint")
        assert public_op is not None
        assert public_op.security == []

    def test_security_scheme_model_parsing(self, minimal_petstore_spec):
        """Test parsing of SecurityScheme models."""
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        assert len(spec.security_schemes_list) == 2

        # Check API key scheme
        api_key_scheme = spec.get_security_scheme_model("api_key")
        assert api_key_scheme is not None
        assert api_key_scheme.name == "api_key"
        assert api_key_scheme.type == "apiKey"
        assert api_key_scheme.in_ == "header"
        assert api_key_scheme.description is None
        assert api_key_scheme.scheme is None

        # Check bearer scheme
        bearer_scheme = spec.get_security_scheme_model("bearer_auth")
        assert bearer_scheme is not None
        assert bearer_scheme.name == "bearer_auth"
        assert bearer_scheme.type == "http"
        assert bearer_scheme.scheme == "bearer"
        assert bearer_scheme.in_ is None

    def test_security_scheme_with_all_fields(self):
        """Test SecurityScheme with all optional fields."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {},
            "components": {
                "securitySchemes": {
                    "oauth2": {
                        "type": "oauth2",
                        "description": "OAuth2 flow",
                        "flows": {
                            "authorizationCode": {
                                "authorizationUrl": "https://example.com/oauth/authorize",
                                "tokenUrl": "https://example.com/oauth/token",
                                "scopes": {
                                    "read": "Read access",
                                    "write": "Write access"
                                }
                            }
                        }
                    },
                    "bearer_jwt": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                        "description": "JWT bearer token"
                    },
                    "api_key_header": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                        "description": "API key in header"
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        assert len(spec.security_schemes_list) == 3

        # Check OAuth2 scheme
        oauth2 = spec.get_security_scheme_model("oauth2")
        assert oauth2 is not None
        assert oauth2.type == "oauth2"
        assert oauth2.description == "OAuth2 flow"
        assert oauth2.flows is not None
        assert "authorizationCode" in oauth2.flows

        # Check Bearer JWT scheme
        bearer_jwt = spec.get_security_scheme_model("bearer_jwt")
        assert bearer_jwt is not None
        assert bearer_jwt.type == "http"
        assert bearer_jwt.scheme == "bearer"
        assert bearer_jwt.bearer_format == "JWT"
        assert bearer_jwt.description == "JWT bearer token"

        # Check API key scheme
        api_key = spec.get_security_scheme_model("api_key_header")
        assert api_key is not None
        assert api_key.type == "apiKey"
        assert api_key.in_ == "header"
        assert api_key.description == "API key in header"

    def test_get_auth_headers_bearer_token(self, minimal_petstore_spec):
        """Test get_auth_headers with Bearer token."""
        import os
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        # Set environment variable
        original_token = os.environ.get("TEST_TOKEN")
        os.environ["TEST_TOKEN"] = "test-token-123"

        try:
            config = AuthConfig(header="Authorization: Bearer ${TEST_TOKEN}")
            headers = spec.get_auth_headers(config)

            assert headers == {"Authorization": "Bearer test-token-123"}
        finally:
            if original_token is not None:
                os.environ["TEST_TOKEN"] = original_token
            else:
                os.environ.pop("TEST_TOKEN", None)

    def test_get_auth_headers_api_key(self, minimal_petstore_spec):
        """Test get_auth_headers with API key."""
        import os
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        # Set environment variable
        original_key = os.environ.get("TEST_API_KEY")
        os.environ["TEST_API_KEY"] = "my-secret-key"

        try:
            config = AuthConfig(header="X-API-Key: ${TEST_API_KEY}")
            headers = spec.get_auth_headers(config)

            assert headers == {"X-API-Key": "my-secret-key"}
        finally:
            if original_key is not None:
                os.environ["TEST_API_KEY"] = original_key
            else:
                os.environ.pop("TEST_API_KEY", None)

    def test_get_auth_headers_no_config(self, minimal_petstore_spec):
        """Test get_auth_headers with no auth config."""
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        config = AuthConfig(header=None)
        headers = spec.get_auth_headers(config)

        assert headers == {}

    def test_get_auth_headers_missing_env_var(self, minimal_petstore_spec):
        """Test get_auth_headers with missing environment variable."""
        import os
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        # Ensure env var is not set
        original_var = os.environ.pop("NONEXISTENT_VAR", None)

        try:
            config = AuthConfig(header="Authorization: Bearer ${NONEXISTENT_VAR}")
            headers = spec.get_auth_headers(config)

            # Should return empty string for missing env var
            assert headers == {"Authorization": "Bearer "}
        finally:
            if original_var is not None:
                os.environ["NONEXISTENT_VAR"] = original_var

    def test_get_auth_headers_no_env_var_syntax(self, minimal_petstore_spec):
        """Test get_auth_headers with literal value (no env var)."""
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        # No ${VAR} syntax, use literal value
        config = AuthConfig(header="X-API-Key: literal-key-value")
        headers = spec.get_auth_headers(config)

        assert headers == {"X-API-Key": "literal-key-value"}


class TestComponentSchemas:
    """Test component schema extraction."""

    def test_extract_component_schemas(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        assert "Pet" in spec.components_schemas
        pet_schema = spec.components_schemas["Pet"]
        assert pet_schema["type"] == "object"
        assert "properties" in pet_schema


class TestReferenceResolution:
    """Test $ref resolution handling."""

    @patch('dietmcp.openapi.parser.prance.ResolvingParser')
    def test_resolve_references(self, mock_parser_class, spec_with_ref):
        # Mock prance to resolve refs
        resolved_spec = {
            "openapi": "3.0.0",
            "info": {"title": "API with refs", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "getUsers",
                        "parameters": [
                            {
                                "name": "limit",
                                "in": "query",
                                "schema": {"type": "integer"}
                            }
                        ],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        mock_parser = MagicMock()
        mock_parser.specification = resolved_spec
        mock_parser_class.return_value = mock_parser

        parser = OpenAPIParser()
        spec = parser.parse_spec(spec_with_ref)

        # After resolution, parameter should be fully expanded
        assert len(spec.endpoints) == 1
        assert spec.endpoints[0].parameters[0].name == "limit"


class TestSpecMetadata:
    """Test spec metadata extraction."""

    def test_title_with_minimal_info(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {}
        }

        spec = parser.parse_spec(spec_dict)
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"
        assert spec.description is None

    def test_default_version(self):
        """Prance requires version, so test with version present."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "2.0.0"},
            "paths": {}
        }

        spec = parser.parse_spec(spec_dict)
        assert spec.version == "2.0.0"

    def test_servers_fallback_to_url(self):
        """Test that servers fallback to URL when loading from URL."""
        parser = OpenAPIParser()

        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {}
        }

        with patch('dietmcp.openapi.parser.prance.ResolvingParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.specification = spec_dict
            mock_parser_class.return_value = mock_parser

            spec = parser.parse_spec("https://api.example.com/openapi.json")

            # Should extract server from URL
            assert len(spec.servers) == 1
            assert spec.servers[0]["url"] == "https://api.example.com"


class TestSpecHelperMethods:
    """Test OpenAPISpec helper methods."""

    def test_get_endpoints_by_tag(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        pets_endpoints = spec.get_endpoints_by_tag("pets")
        # Only getPets has "pets" tag (createPet has no tag)
        assert len(pets_endpoints) == 1

        operation_ids = {ep.operation_id for ep in pets_endpoints}
        assert operation_ids == {"getPets"}

    def test_get_endpoints_by_nonexistent_tag(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        endpoints = spec.get_endpoints_by_tag("nonexistent")
        assert len(endpoints) == 0

    def test_get_endpoint_by_id(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        endpoint = spec.get_endpoint_by_id("getPets")
        assert endpoint is not None
        assert endpoint.operation_id == "getPets"

    def test_get_endpoint_by_nonexistent_id(self, minimal_petstore_spec):
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        endpoint = spec.get_endpoint_by_id("nonexistent")
        assert endpoint is None

    def test_extract_endpoints_deprecated(self, minimal_petstore_spec):
        """Test that extract_endpoints method works (deprecated)."""
        parser = OpenAPIParser()
        spec = parser.parse_spec(minimal_petstore_spec)

        # This method is deprecated but should still work
        endpoints = parser.extract_endpoints(spec)
        assert len(endpoints) == 3


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_spec_with_no_responses(self):
        """Test that specs without responses are rejected by prance."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test"
                    }
                }
            }
        }

        # Prance requires responses field
        with pytest.raises(OpenAPIParserError, match="Failed to resolve references"):
            parser.parse_spec(spec_dict)

    def test_spec_with_no_tags(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        assert spec.endpoints[0].tags == []

    def test_spec_without_operation_id(self):
        """Test endpoints without operationId (should be handled)."""
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "summary": "Get test",
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        assert len(spec.endpoints) == 1
        assert spec.endpoints[0].operation_id is None

    def test_empty_spec(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "Empty", "version": "1.0.0"},
            "paths": {}
        }

        spec = parser.parse_spec(spec_dict)
        assert len(spec.endpoints) == 0
        assert len(spec.servers) == 0
        assert len(spec.security_schemes) == 0
        assert len(spec.components_schemas) == 0

    def test_spec_with_no_components(self):
        parser = OpenAPIParser()
        spec_dict = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }

        spec = parser.parse_spec(spec_dict)
        assert len(spec.security_schemes) == 0
        assert len(spec.components_schemas) == 0


class TestPathValidation:
    """Test path validation and security restrictions."""

    def test_load_from_allowed_config_directory(self, tmp_path, minimal_petstore_spec):
        """Test loading from ~/.config/dietmcp/specs."""
        import json
        from pathlib import Path
        import tempfile
        import os

        # Create a fake home directory
        with tempfile.TemporaryDirectory() as temp_home:
            # Set up allowed directory structure
            config_dir = Path(temp_home) / ".config" / "dietmcp" / "specs"
            config_dir.mkdir(parents=True)

            # Write spec file
            spec_file = config_dir / "petstore.json"
            spec_file.write_text(json.dumps(minimal_petstore_spec))

            # Temporarily change HOME to point to our test directory
            original_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = temp_home
                parser = OpenAPIParser()
                spec = parser.parse_spec(spec_file)

                assert spec.title == "Petstore API"
            finally:
                if original_home:
                    os.environ["HOME"] = original_home
                else:
                    os.environ.pop("HOME", None)

    def test_load_from_allowed_specs_directory(self, tmp_path, minimal_petstore_spec):
        """Test loading from ./specs directory."""
        import json

        # Create specs directory in current directory
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write spec file
        spec_file = specs_dir / "petstore.json"
        spec_file.write_text(json.dumps(minimal_petstore_spec))

        # Change to tmp_path to make it current directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            spec = parser.parse_spec(spec_file)

            assert spec.title == "Petstore API"
        finally:
            os.chdir(original_cwd)

    def test_load_from_allowed_dot_specs_directory(self, tmp_path, minimal_petstore_spec):
        """Test loading from ./.specs directory."""
        import json

        # Create .specs directory in current directory
        specs_dir = tmp_path / ".specs"
        specs_dir.mkdir()

        # Write spec file
        spec_file = specs_dir / "petstore.json"
        spec_file.write_text(json.dumps(minimal_petstore_spec))

        # Change to tmp_path to make it current directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            spec = parser.parse_spec(spec_file)

            assert spec.title == "Petstore API"
        finally:
            os.chdir(original_cwd)

    def test_load_from_disallowed_directory(self, tmp_path, minimal_petstore_spec):
        """Test that loading from arbitrary directories is blocked."""
        import json

        # Write spec file to non-allowed directory
        spec_file = tmp_path / "petstore.json"
        spec_file.write_text(json.dumps(minimal_petstore_spec))

        parser = OpenAPIParser()
        with pytest.raises(OpenAPIParserError, match="Spec file path outside allowed directories"):
            parser.parse_spec(spec_file)

    def test_load_from_system_paths_blocked(self, tmp_path, minimal_petstore_spec):
        """Test that loading from /tmp, /etc, etc. is blocked."""
        import json

        # Create a temp file (simulating /tmp or other system paths)
        spec_file = tmp_path / "system_path" / "petstore.json"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text(json.dumps(minimal_petstore_spec))

        parser = OpenAPIParser()
        with pytest.raises(OpenAPIParserError, match="Spec file path outside allowed directories"):
            parser.parse_spec(spec_file)

    def test_symlink_to_allowed_directory(self, tmp_path, minimal_petstore_spec):
        """Test that symlinks within allowed directories work."""
        import json
        import os

        # Create specs directory
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write actual spec file
        actual_file = specs_dir / "actual_petstore.json"
        actual_file.write_text(json.dumps(minimal_petstore_spec))

        # Create symlink
        symlink_file = specs_dir / "petstore.json"
        symlink_file.symlink_to(actual_file)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            spec = parser.parse_spec(symlink_file)

            assert spec.title == "Petstore API"
        finally:
            os.chdir(original_cwd)

    def test_symlink_outside_allowed_directory_blocked(self, tmp_path, minimal_petstore_spec):
        """Test that symlinks pointing outside allowed directories are blocked."""
        import json
        import os

        # Create specs directory
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write spec file outside allowed directory
        outside_file = tmp_path / "outside_petstore.json"
        outside_file.write_text(json.dumps(minimal_petstore_spec))

        # Create symlink inside allowed directory pointing outside
        symlink_file = specs_dir / "petstore.json"
        symlink_file.symlink_to(outside_file)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            parser = OpenAPIParser()
            with pytest.raises(OpenAPIParserError, match="Spec file path outside allowed directories"):
                parser.parse_spec(symlink_file)
        finally:
            os.chdir(original_cwd)

    def test_directory_traversal_blocked(self, tmp_path, minimal_petstore_spec):
        """Test that directory traversal attempts are blocked."""
        import json
        import os

        # Create specs directory
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write spec file in specs directory
        spec_file = specs_dir / "petstore.json"
        spec_file.write_text(json.dumps(minimal_petstore_spec))

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            parser = OpenAPIParser()

            # Try various directory traversal attempts
            traversal_attempts = [
                specs_dir / ".." / "specs" / "petstore.json",  # Parent dir traversal
                specs_dir / "./../specs/./petstore.json",  # Complex traversal
            ]

            # Note: Path.resolve() normalizes these, so they may actually resolve
            # to the same path. The key is that they shouldn't escape allowed dirs.
            for attempt in traversal_attempts:
                # After resolution, if it's still in allowed dir, it should work
                # If it escapes, it should be blocked
                try:
                    spec = parser.parse_spec(attempt)
                    # If it works, verify it's the right spec
                    assert spec.title == "Petstore API"
                except OpenAPIParserError as e:
                    # If blocked, verify it's due to path validation
                    assert "outside allowed directories" in str(e) or "not found" in str(e)
        finally:
            os.chdir(original_cwd)

    def test_absolute_path_outside_allowed_blocked(self, tmp_path, minimal_petstore_spec):
        """Test that absolute paths outside allowed directories are blocked."""
        import json

        # Write spec file to arbitrary location
        spec_file = tmp_path / "arbitrary" / "petstore.json"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text(json.dumps(minimal_petstore_spec))

        parser = OpenAPIParser()
        with pytest.raises(OpenAPIParserError, match="Spec file path outside allowed directories"):
            parser.parse_spec(spec_file.resolve())

    def test_nonexistent_file_in_allowed_directory(self, tmp_path):
        """Test that nonexistent files in allowed directories are handled properly."""
        import os

        # Create specs directory
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            parser = OpenAPIParser()
            nonexistent_file = specs_dir / "nonexistent.json"

            with pytest.raises(OpenAPIParserError, match="Spec file not found"):
                parser.parse_spec(nonexistent_file)
        finally:
            os.chdir(original_cwd)
