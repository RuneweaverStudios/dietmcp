"""Example: Integrating OpenAPI tools with skills_generator.

This demonstrates how to:
1. Parse an OpenAPI spec
2. Generate ToolDefinition objects
3. Create a unified skill summary
"""

from dietmcp.openapi.generator import OpenAPIToolGenerator
from dietmcp.models.openapi import OpenAPISpec, OpenAPIEndpoint
from dietmcp.models.skill import SkillCategory, SkillSummary, SkillEntry
from dietmcp.models.tool import ToolDefinition


def example_petstore_api():
    """Example using Petstore-like OpenAPI spec."""

    # Create a sample OpenAPI spec (normally parsed from a file/URL)
    spec = OpenAPISpec(
        title="Petstore API",
        version="1.0.0",
        description="Sample Pet Store API",
        endpoints=[
            # GET /pets - List all pets
            OpenAPIEndpoint(
                path="/pets",
                method="GET",
                operation_id="getPets",
                summary="List all pets",
                parameters=[
                    {
                        "name": "limit",
                        "in_": "query",
                        "required": False,
                        "schema_": {"type": "integer"},
                    }
                ],
            ),
            # GET /pets/{id} - Get pet by ID
            OpenAPIEndpoint(
                path="/pets/{id}",
                method="GET",
                operation_id="getPetById",
                summary="Get pet by ID",
                parameters=[
                    {
                        "name": "id",
                        "in_": "path",
                        "required": True,
                        "schema_": {"type": "string"},
                    }
                ],
            ),
            # POST /pets - Create a pet
            OpenAPIEndpoint(
                path="/pets",
                method="POST",
                operation_id="createPet",
                summary="Create a new pet",
                request_body={
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "tag": {"type": "string"},
                                },
                                "required": ["name"],
                            }
                        }
                    }
                },
            ),
            # DELETE /pets/{id} - Delete a pet
            OpenAPIEndpoint(
                path="/pets/{id}",
                method="DELETE",
                operation_id="deletePet",
                summary="Delete a pet",
                parameters=[
                    {
                        "name": "id",
                        "in_": "path",
                        "required": True,
                        "schema_": {"type": "string"},
                    }
                ],
            ),
        ],
    )

    # Generate ToolDefinition objects
    generator = OpenAPIToolGenerator()
    tools = generator.generate_tools(spec, server_name="petstore", ultra_compact=True)

    print(f"Generated {len(tools)} tools from OpenAPI spec:\n")

    for tool in tools:
        signature = tool.compact_signature(ultra_compact=True)
        print(f"  {signature}")
        print(f"    → {tool.description}\n")

    # Create skill summary (compatible with skills_generator output)
    categories = [
        SkillCategory(
            name="Pet Operations",
            tools=tuple(
                SkillEntry(
                    signature=tool.compact_signature(ultra_compact=True),
                    description=tool.description[:40],
                )
                for tool in tools
            ),
        )
    ]

    summary = SkillSummary(
        server_name="petstore",
        tool_count=len(tools),
        categories=tuple(categories),
        exec_syntax="dietmcp exec petstore <tool> --args '{\"key\": \"value\"}'",
        ultra_compact=True,
    )

    print("\n=== Skill Summary (Ultra-Compact) ===")
    print(f"Server: {summary.server_name}")
    print(f"Tools: {summary.tool_count}")
    print(f"Format: {'Ultra-Compact' if summary.ultra_compact else 'Standard'}")
    print(f"\nCategories:")
    for category in summary.categories:
        print(f"\n  {category.name}:")
        for tool in category.tools:
            print(f"    {tool.signature}")
            print(f"      {tool.description}")

    print(f"\nExecution: {summary.exec_syntax}")


def example_signature_comparison():
    """Compare standard vs ultra-compact signatures."""

    endpoint = OpenAPIEndpoint(
        path="/users/{id}",
        method="GET",
        operation_id="getUserById",
        summary="Get user by ID with optional filters",
        parameters=[
            {
                "name": "id",
                "in_": "path",
                "required": True,
                "schema_": {"type": "string"},
            },
            {
                "name": "limit",
                "in_": "query",
                "required": False,
                "schema_": {"type": "integer"},
            },
            {
                "name": "sort",
                "in_": "query",
                "required": False,
                "schema_": {"type": "string", "enum": ["asc", "desc"]},
            },
            {
                "name": "fields",
                "in_": "query",
                "required": False,
                "schema_": {"type": "array", "items": {"type": "string"}},
            },
        ],
    )

    generator = OpenAPIToolGenerator()
    tool = generator._generate_tool(endpoint, "testapi", ultra_compact=False)

    print("=== Signature Format Comparison ===\n")
    print("Standard Compact (29 tokens/tool):")
    print(f"  {tool.compact_signature(ultra_compact=False)}")
    print(f"  → {tool.description}\n")

    print("Ultra-Compact (13-15 tokens/tool):")
    print(f"  {tool.compact_signature(ultra_compact=True)}")
    print(f"  → {tool.description[:40]}...\n")

    print("Token Savings:")
    print(f"  Standard: ~29 tokens")
    print(f"  Ultra: ~14 tokens")
    print(f"  Savings: ~52%")


if __name__ == "__main__":
    print("=" * 60)
    print("OpenAPI Tool Generator Integration Examples")
    print("=" * 60)
    print()

    example_petstore_api()
    print("\n" + "=" * 60 + "\n")
    example_signature_comparison()
