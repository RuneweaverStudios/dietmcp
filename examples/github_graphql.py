"""Example: Using GitHub GraphQL API with dietmcp.

This example demonstrates:
1. Configuration setup for GraphQL server
2. Native introspection for tool discovery
3. Executing GraphQL-generated tools
4. Common GitHub operations
"""

import json
import subprocess
import os


def run_command(cmd: list[str]) -> str:
    """Run a shell command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def check_github_token() -> bool:
    """Check if GitHub token is available."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("⚠️  WARNING: GITHUB_TOKEN environment variable not set!")
        print("Set it with: export GITHUB_TOKEN=ghp_your_token_here")
        return False
    return True


def example_github_config():
    """Example configuration for GitHub GraphQL server.

    Add this to your dietmcp config file (run `dietmcp config path` to find it):
    """

    config = {
        "graphqlServers": {
            "github": {
                "url": "https://api.github.com/graphql",
                "auth": {
                    "header": "Authorization: Bearer ${GITHUB_TOKEN}"
                }
            }
        }
    }

    print("=== GitHub GraphQL Configuration ===")
    print(json.dumps(config, indent=2))
    print()


def example_discover_tools():
    """Discover tools from GitHub GraphQL introspection."""
    print("=== Discovering GitHub GraphQL Tools ===")
    print("Command: dietmcp discover github")
    print()

    if not check_github_token():
        print("Skipping discovery (no token)")
        return

    output = run_command(["dietmcp", "discover", "github"])
    print(output)
    print()


def example_skill_summary():
    """Generate ultra-compact skill summary."""
    print("=== Generating Ultra-Compact Summary ===")
    print("Command: dietmcp skills github --format ultra")
    print()

    if not check_github_token():
        print("Skipping skill generation (no token)")
        return

    output = run_command(["dietmcp", "skills", "github", "--format", "ultra"])
    print(output)
    print()


def example_get_repository():
    """Example: Get repository details."""
    print("=== Example: Get Repository ===")
    print("Command: dietmcp exec github getRepository --args '{\"owner\": \"anthropics\", \"name\": \"claude-code\"}'")
    print()

    if not check_github_token():
        print("Skipping (no token)")
        return

    output = run_command([
        "dietmcp", "exec", "github", "getRepository",
        "--args", '{"owner": "anthropics", "name": "claude-code"}'
    ])
    print(output)
    print()


def example_search_repositories():
    """Example: Search repositories."""
    print("=== Example: Search Repositories ===")
    print("Command: dietmcp exec github searchRepositories --args '{\"query\": \"language:python stars:>1000\", \"first\": 5}'")
    print()

    if not check_github_token():
        print("Skipping (no token)")
        return

    output = run_command([
        "dietmcp", "exec", "github", "searchRepositories",
        "--args", '{"query": "language:python stars:>1000", "first": 5}'
    ])
    print(output)
    print()


def example_get_issue():
    """Example: Get issue details."""
    print("=== Example: Get Issue ===")
    print("Command: dietmcp exec github getIssue --args '{\"owner\": \"anthropics\", \"name\": \"claude-code\", \"number\": 1}'")
    print()

    if not check_github_token():
        print("Skipping (no token)")
        return

    output = run_command([
        "dietmcp", "exec", "github", "getIssue",
        "--args", '{"owner": "anthropics", "name": "claude-code", "number": 1}'
    ])
    print(output)
    print()


def example_output_formats():
    """Example: Different output formats."""
    print("=== Example: Output Formats ===")

    if not check_github_token():
        print("Skipping (no token)")
        return

    # Summary format (default)
    print("\n1. Summary format (default, LLM-friendly):")
    output = run_command([
        "dietmcp", "exec", "github", "getRepository",
        "--args", '{"owner": "anthropics", "name": "claude-code"}'
    ])
    print(output[:500])  # Show first 500 chars

    # Minified format
    print("\n2. Minified JSON format:")
    output = run_command([
        "dietmcp", "exec", "github", "getRepository",
        "--args", '{"owner": "anthropics", "name": "claude-code"}',
        "--output-format", "minified"
    ])
    print(output[:500])  # Show first 500 chars

    # TOON format (if applicable)
    print("\n3. TOON format (40-60% smaller):")
    output = run_command([
        "dietmcp", "exec", "github", "searchRepositories",
        "--args", '{"query": "language:python", "first": 3}',
        "--output-format", "toon"
    ])
    print(output[:500])  # Show first 500 chars


def example_list_repository_issues():
    """Example: List repository issues."""
    print("=== Example: List Repository Issues ===")
    print("Command: dietmcp exec github listRepositoryIssues --args '{\"owner\": \"anthropics\", \"name\": \"claude-code\", \"first\": 10}'")
    print()

    if not check_github_token():
        print("Skipping (no token)")
        return

    output = run_command([
        "dietmcp", "exec", "github", "listRepositoryIssues",
        "--args", '{"owner": "anthropics", "name": "claude-code", "first": 10}'
    ])
    print(output)
    print()


def example_get_user_profile():
    """Example: Get user profile."""
    print("=== Example: Get User Profile ===")
    print("Command: dietmcp exec github getUser --args '{\"login\": \"torvalds\"}'")
    print()

    if not check_github_token():
        print("Skipping (no token)")
        return

    output = run_command([
        "dietmcp", "exec", "github", "getUser",
        "--args", '{"login": "torvalds"}'
    ])
    print(output)
    print()


def example_compare_with_rest():
    """Example: Compare GraphQL vs REST approach."""
    print("=== Example: GraphQL vs REST ===")
    print()

    print("GraphQL advantages:")
    print("- Single query fetches exactly what you need")
    print("- No over-fetching or under-fetching")
    print("- Strongly typed schema via introspection")
    print("- Real-time schema discovery")
    print()

    print("dietmcp benefits:")
    print("- Automatic introspection (no manual schema files)")
    print("- Ultra-compact tool summaries (13-16 tokens/tool)")
    print("- Unified CLI interface (same as MCP and OpenAPI)")
    print("- Multiple output formats (summary, minified, CSV, TOON)")
    print()


def main():
    """Run all examples."""
    print("=" * 70)
    print("GitHub GraphQL API Examples with dietmcp")
    print("=" * 70)
    print()

    # Check for token
    if not check_github_token():
        print("\n⚠️  Most examples require a GitHub token.")
        print("Get one here: https://github.com/settings/tokens")
        print("Set it with: export GITHUB_TOKEN=ghp_your_token_here")
        print()

    # Configuration
    example_github_config()

    # Discovery
    example_discover_tools()
    example_skill_summary()

    # Common operations
    example_get_repository()
    example_search_repositories()
    example_get_issue()
    example_list_repository_issues()
    example_get_user_profile()

    # Output formats
    example_output_formats()

    # Comparison
    example_compare_with_rest()

    print("=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
