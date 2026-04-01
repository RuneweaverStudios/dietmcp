"""Example: Using the Petstore OpenAPI API with dietmcp.

This example demonstrates:
1. Configuration setup for OpenAPI server
2. Tool discovery from OpenAPI spec
3. Executing OpenAPI-generated tools
4. Using different output formats
"""

import json
import subprocess


def run_command(cmd: list[str]) -> str:
    """Run a shell command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def example_petstore_config():
    """Example configuration for Petstore OpenAPI server.

    Add this to your dietmcp config file (run `dietmcp config path` to find it):
    """

    config = {
        "openapiServers": {
            "petstore": {
                "url": "https://petstore.swagger.io/v2/swagger.json",
                "baseUrl": "https://petstore.swagger.io/v2",
                "auth": None  # No auth required for public Petstore API
            }
        }
    }

    print("=== Petstore Configuration ===")
    print(json.dumps(config, indent=2))
    print()


def example_discover_tools():
    """Discover tools from Petstore OpenAPI spec."""
    print("=== Discovering Petstore Tools ===")
    print("Command: dietmcp discover petstore")
    print()

    output = run_command(["dietmcp", "discover", "petstore"])
    print(output)
    print()


def example_skill_summary():
    """Generate ultra-compact skill summary."""
    print("=== Generating Ultra-Compact Summary ===")
    print("Command: dietmcp skills petstore --format ultra")
    print()

    output = run_command(["dietmcp", "skills", "petstore", "--format", "ultra"])
    print(output)
    print()


def example_list_pets():
    """Example: List all pets."""
    print("=== Example: List All Pets ===")
    print("Command: dietmcp exec petstore getPets --args '{}'")
    print()

    output = run_command([
        "dietmcp", "exec", "petstore", "getPets",
        "--args", "{}"
    ])
    print(output)
    print()


def example_get_pet_by_id():
    """Example: Get specific pet by ID."""
    print("=== Example: Get Pet by ID ===")
    print("Command: dietmcp exec petstore getPetById --args '{\"id\": \"1\"}'")
    print()

    output = run_command([
        "dietmcp", "exec", "petstore", "getPetById",
        "--args", '{"id": "1"}'
    ])
    print(output)
    print()


def example_list_pets_with_limit():
    """Example: List pets with limit parameter."""
    print("=== Example: List Pets with Limit ===")
    print("Command: dietmcp exec petstore getPets --args '{\"limit\": 5}'")
    print()

    output = run_command([
        "dietmcp", "exec", "petstore", "getPets",
        "--args", '{"limit": 5}'
    ])
    print(output)
    print()


def example_output_formats():
    """Example: Different output formats."""
    print("=== Example: Output Formats ===")

    # Summary format (default)
    print("\n1. Summary format (default, LLM-friendly):")
    output = run_command([
        "dietmcp", "exec", "petstore", "getPets",
        "--args", "{}"
    ])
    print(output[:500])  # Show first 500 chars

    # Minified format
    print("\n2. Minified JSON format:")
    output = run_command([
        "dietmcp", "exec", "petstore", "getPets",
        "--args", "{}",
        "--output-format", "minified"
    ])
    print(output[:500])  # Show first 500 chars

    # TOON format (if applicable)
    print("\n3. TOON format (40-60% smaller):")
    output = run_command([
        "dietmcp", "exec", "petstore", "getPets",
        "--args", "{}",
        "--output-format", "toon"
    ])
    print(output[:500])  # Show first 500 chars


def example_create_pet():
    """Example: Create a new pet."""
    print("=== Example: Create New Pet ===")
    print("Command: dietmcp exec petstore createPet --args '{\"name\": \"Fluffy\", \"status\": \"available\"}'")
    print()

    output = run_command([
        "dietmcp", "exec", "petstore", "createPet",
        "--args", '{"name": "Fluffy", "status": "available"}'
    ])
    print(output)
    print()


def example_delete_pet():
    """Example: Delete a pet."""
    print("=== Example: Delete Pet ===")
    print("Command: dietmcp exec petstore deletePet --args '{\"id\": \"1\"}'")
    print()

    output = run_command([
        "dietmcp", "exec", "petstore", "deletePet",
        "--args", '{"id": "1"}'
    ])
    print(output)
    print()


def main():
    """Run all examples."""
    print("=" * 70)
    print("Petstore OpenAPI API Examples with dietmcp")
    print("=" * 70)
    print()

    # Configuration
    example_petstore_config()

    # Discovery
    example_discover_tools()
    example_skill_summary()

    # Basic operations
    example_list_pets()
    example_get_pet_by_id()
    example_list_pets_with_limit()

    # Output formats
    example_output_formats()

    # Write operations (commented out to avoid modifying data)
    # example_create_pet()
    # example_delete_pet()

    print("=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
