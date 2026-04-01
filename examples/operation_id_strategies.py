#!/usr/bin/env python3
"""Example demonstrating operation ID generation strategies.

This script shows how different operation ID strategies transform
OpenAPI endpoints into tool names.
"""

from dietmcp.openapi.generator import generate_operation_id, OperationIDStrategy
from dietmcp.models.openapi import OpenAPIEndpoint


def main():
    """Demonstrate all operation ID strategies."""
    # Sample endpoints
    endpoints = [
        OpenAPIEndpoint(
            path="/users/{id}",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        ),
        OpenAPIEndpoint(
            path="/api/v1/users/{userId}/posts/{postId}",
            method="POST",
            operation_id="createUserPost",  # Existing operationId
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        ),
        OpenAPIEndpoint(
            path="/products",
            method="GET",
            operation_id=None,
            parameters=[],
            request_body=None,
            responses={},
            tags=[],
        ),
    ]

    strategies = [
        OperationIDStrategy.AUTO,
        OperationIDStrategy.PATH_METHOD,
        OperationIDStrategy.PATH_LOWER,
        OperationIDStrategy.CAMEL_CASE,
        OperationIDStrategy.SNAKE_CASE,
        OperationIDStrategy.KEBAB_CASE,
    ]

    for endpoint in endpoints:
        print(f"\nEndpoint: {endpoint.method} {endpoint.path}")
        print(f"Existing operationId: {endpoint.operation_id}")
        print("-" * 80)

        for strategy in strategies:
            op_id = generate_operation_id(endpoint, strategy)
            print(f"  {strategy.value:20s}: {op_id}")


if __name__ == "__main__":
    main()
