"""OpenAPI specification parsing utilities."""

from dietmcp.openapi.parser import OpenAPIParser, OpenAPIParserError
from dietmcp.openapi.generator import (
    OpenAPIToolGenerator,
    generate_signature,
    generate_operation_id,
    OperationIDStrategy,
)
from dietmcp.openapi.executor import OpenAPIExecutor, OpenAPIExecutorError
from dietmcp.models.openapi import (
    OpenAPISpec,
    OpenAPIEndpoint,
    OpenAPIParameter,
)

__all__ = [
    "OpenAPIParser",
    "OpenAPIParserError",
    "OpenAPIToolGenerator",
    "generate_signature",
    "generate_operation_id",
    "OperationIDStrategy",
    "OpenAPIExecutor",
    "OpenAPIExecutorError",
    "OpenAPISpec",
    "OpenAPIEndpoint",
    "OpenAPIParameter",
]
