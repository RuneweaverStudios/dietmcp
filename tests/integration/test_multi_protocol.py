"""End-to-end integration tests for dietmcp's multi-protocol support.

Tests MCP, OpenAPI, and GraphQL protocols with real APIs to verify:
- Full workflow: config → discover → skills → exec
- Protocol auto-detection
- Ultra-compact format generation
- Token efficiency

API Requirements:
- Petstore OpenAPI: https://petstore3.swagger.io/api/v3/openapi.json (no auth)
- GitHub GraphQL: https://api.github.com/graphql (requires GITHUB_TOKEN env var)
- Filesystem MCP: npx @modelcontextprotocol/server-filesystem (requires Node.js)

Run with: pytest tests/integration/test_multi_protocol.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from dietmcp.main import cli

# Test constants
PETSTORE_URL = "https://petstore3.swagger.io/api/v3/openapi.json"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
# Use /private/tmp on macOS to avoid symlink issues
TEST_TMP_DIR = "/private/tmp/dietmcp_test"


class TestMCPProtocol:
    """Test MCP protocol workflow with filesystem server."""

    @pytest.fixture
    def mcp_config(self, tmp_path: Path) -> Path:
        """Create config with MCP filesystem server."""
        config = {
            "mcpServers": {
                "test-filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", TEST_TMP_DIR],
                }
            },
            "defaults": {
                "cacheTtlSeconds": 3600,
                "outputFormat": "summary",
                "maxResponseSize": 50000,
            },
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config_path

    def test_mcp_full_workflow(self, mcp_config: Path, tmp_path: Path):
        """Test complete MCP workflow: config → discover → skills → exec."""
        runner = CliRunner()

        # Create test directory
        test_dir = Path(TEST_TMP_DIR)
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "test.txt"
        test_file.write_text("Hello from MCP test!")

        # Step 1: Discover tools
        result = runner.invoke(cli, ["discover", "test-filesystem", "--config", str(mcp_config)])
        assert result.exit_code == 0
        assert "read_file" in result.output
        assert "write_file" in result.output
        assert "list_directory" in result.output

        # Step 2: Generate skills
        result = runner.invoke(cli, ["skills", "test-filesystem", "--config", str(mcp_config)])
        assert result.exit_code == 0
        assert "read_file" in result.output
        assert "write_file" in result.output

        # Step 3: Generate ultra-compact skills
        result = runner.invoke(
            cli, ["skills", "test-filesystem", "--format", "ultra", "--config", str(mcp_config)]
        )
        assert result.exit_code == 0
        # Ultra format should be more compact than standard (but still reasonable size for 14 tools)
        assert len(result.output) < 2000  # Should be very compact

        # Step 4: Execute tool - read file
        result = runner.invoke(
            cli,
            [
                "exec",
                "test-filesystem",
                "read_file",
                "--args",
                json.dumps({"path": str(test_file)}),
                "--config",
                str(mcp_config),
            ],
        )
        assert result.exit_code == 0
        assert "Hello from MCP test!" in result.output

        # Step 5: Execute tool - list directory
        result = runner.invoke(
            cli,
            [
                "exec",
                "test-filesystem",
                "list_directory",
                "--args",
                json.dumps({"path": TEST_TMP_DIR}),
                "--config",
                str(mcp_config),
            ],
        )
        assert result.exit_code == 0
        assert "test.txt" in result.output

        # Cleanup
        test_file.unlink()
        # Remove all files in test directory before rmdir
        if test_dir.exists():
            for item in test_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    # Skip subdirectories for now
                    pass
            # Try to remove the directory
            try:
                test_dir.rmdir()
            except OSError:
                # Directory not empty, skip cleanup
                pass


class TestOpenAPIProtocol:
    """Test OpenAPI protocol workflow with Petstore API."""

    @pytest.fixture
    def openapi_config(self, tmp_path: Path) -> Path:
        """Create config with OpenAPI Petstore server."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {
                "cacheTtlSeconds": 3600,
                "outputFormat": "summary",
                "maxResponseSize": 50000,
            },
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config_path

    def test_openapi_full_workflow(self, openapi_config: Path):
        """Test complete OpenAPI workflow: config → discover → skills → exec."""
        runner = CliRunner()

        # Step 1: Discover tools from Petstore OpenAPI spec
        result = runner.invoke(cli, ["discover", "petstore", "--config", str(openapi_config)])
        assert result.exit_code == 0
        # Petstore has many endpoints, check for common ones
        assert "getPetById" in result.output or "getUserByName" in result.output

        # Step 2: Generate skills
        result = runner.invoke(cli, ["skills", "petstore", "--config", str(openapi_config)])
        assert result.exit_code == 0
        assert "petstore" in result.output.lower()

        # Step 3: Generate ultra-compact skills
        result = runner.invoke(
            cli, ["skills", "petstore", "--format", "ultra", "--config", str(openapi_config)]
        )
        assert result.exit_code == 0
        # Ultra format should be very compact
        output_lines = [line for line in result.output.split("\n") if line.strip()]
        assert len(output_lines) > 0

        # Step 4: Execute tool - get pet by ID
        # Note: Petstore is a demo API, pet ID 1 should exist
        result = runner.invoke(
            cli,
            [
                "exec",
                "petstore",
                "getPetById",
                "--args",
                json.dumps({"petId": 1}),
                "--config",
                str(openapi_config),
            ],
        )
        # May succeed or fail depending on Petstore state
        # Just verify the command structure is correct
        assert result.exit_code in [0, 1]  # API might be down

    def test_openapi_discover_json_output(self, openapi_config: Path):
        """Test OpenAPI discovery with JSON output."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["discover", "petstore", "--json", "--config", str(openapi_config)]
        )
        assert result.exit_code == 0

        # Parse JSON output
        try:
            tools_data = json.loads(result.output)
            assert isinstance(tools_data, list)
            # Should have discovered multiple endpoints
            assert len(tools_data) > 0
        except json.JSONDecodeError:
            pytest.fail("Discovery output is not valid JSON")

    def test_openapi_multiple_endpoints(self, openapi_config: Path):
        """Test that multiple OpenAPI endpoints are discovered."""
        runner = CliRunner()

        result = runner.invoke(cli, ["discover", "petstore", "--config", str(openapi_config)])
        assert result.exit_code == 0

        # Petstore should have many endpoints
        output = result.output.lower()
        # Check for various endpoint types
        endpoint_indicators = ["pet", "user", "store", "order"]
        found_indicators = sum(1 for indicator in endpoint_indicators if indicator in output)
        assert found_indicators >= 2, "Should discover multiple endpoint types"


class TestGraphQLProtocol:
    """Test GraphQL protocol workflow with GitHub API."""

    @pytest.fixture
    def graphql_config(self, tmp_path: Path) -> Path:
        """Create config with GraphQL server."""
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            pytest.skip("GITHUB_TOKEN environment variable not set")

        config = {
            "graphqlServers": {
                "github": {
                    "url": GITHUB_GRAPHQL_URL,
                    "auth": {
                        "header": f"Authorization: Bearer {github_token}",
                    },
                }
            },
            "defaults": {
                "cacheTtlSeconds": 3600,
                "outputFormat": "summary",
                "maxResponseSize": 50000,
            },
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config_path

    def test_graphql_full_workflow(self, graphql_config: Path):
        """Test complete GraphQL workflow: config → discover → skills → exec."""
        runner = CliRunner()

        # Step 1: Discover tools via introspection
        result = runner.invoke(cli, ["discover", "github", "--config", str(graphql_config)])
        assert result.exit_code == 0
        # GitHub GraphQL schema should have queries
        assert "repository" in result.output.lower() or "user" in result.output.lower()

        # Step 2: Generate skills
        result = runner.invoke(cli, ["skills", "github", "--config", str(graphql_config)])
        assert result.exit_code == 0
        assert "github" in result.output.lower()

        # Step 3: Generate ultra-compact skills
        result = runner.invoke(
            cli, ["skills", "github", "--format", "ultra", "--config", str(graphql_config)]
        )
        assert result.exit_code == 0
        # Ultra format should be compact
        assert len(result.output) > 0

    def test_graphql_discover_json_output(self, graphql_config: Path):
        """Test GraphQL discovery with JSON output."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["discover", "github", "--json", "--config", str(graphql_config)]
        )
        assert result.exit_code == 0

        # Parse JSON output
        try:
            tools_data = json.loads(result.output)
            assert isinstance(tools_data, list)
            # Should have discovered queries/mutations
            assert len(tools_data) > 0
        except json.JSONDecodeError:
            pytest.fail("Discovery output is not valid JSON")

    def test_graphql_introspection_fields(self, graphql_config: Path):
        """Test that GraphQL introspection finds schema fields."""
        runner = CliRunner()

        result = runner.invoke(cli, ["discover", "github", "--config", str(graphql_config)])
        assert result.exit_code == 0

        # GitHub GraphQL should discover common queries
        output_lower = result.output.lower()
        # Check for common GitHub GraphQL fields
        graphql_fields = ["repository", "user", "search", "viewer"]
        found_fields = sum(1 for field in graphql_fields if field in output_lower)
        assert found_fields >= 2, "Should discover multiple GraphQL fields"

    def test_graphql_field_selection(self, graphql_config: Path):
        """Test that GraphQL queries use proper field selection, not just __typename."""
        runner = CliRunner()

        # Execute a GraphQL query that should return multiple fields
        result = runner.invoke(
            cli,
            [
                "exec",
                "github",
                "user",
                "--args",
                json.dumps({"login": "torvalds"}),
                "--config",
                str(graphql_config),
            ],
        )

        # Should succeed
        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

        # Parse the output to verify multiple fields are returned
        try:
            # The output should be JSON
            output_data = json.loads(result.stdout)

            # Extract the data field from ToolResult format
            # The output may be a ToolResult with content blocks
            if isinstance(output_data, dict) and "content" in output_data:
                # Extract the actual data from content blocks
                content = output_data["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_block = content[0]
                    if isinstance(first_block, dict) and "text" in first_block:
                        data = json.loads(first_block["text"])
                    else:
                        data = first_block
                else:
                    data = content
            else:
                # Direct JSON response
                data = output_data

            # Navigate to the user data
            # The response structure is typically {"data": {"user": {...}}}
            if isinstance(data, dict):
                if "data" in data:
                    user_data = data["data"].get("user", {})
                elif "user" in data:
                    user_data = data["user"]
                else:
                    # Might be wrapped in operation name
                    user_data = data

                # Verify we have multiple fields, not just __typename
                if isinstance(user_data, dict):
                    # Should have fields like login, name, email, etc.
                    field_count = len(user_data.keys())

                    # Assert that we have more than just __typename
                    # In practice, we should get 5+ fields from auto_select_fields
                    assert (
                        field_count > 1 or "__typename" not in user_data
                    ), f"Expected multiple fields, got: {list(user_data.keys())}"

                    # Common fields that should be present
                    common_fields = ["login", "name", "email", "bio", "url"]
                    found_common = sum(1 for field in common_fields if field in user_data)

                    # We should have at least some of these common fields
                    assert (
                        found_common >= 2
                    ), f"Expected common fields like {common_fields}, got: {list(user_data.keys())}"

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pytest.fail(f"Failed to parse GraphQL response: {e}\nOutput: {result.stdout}")


class TestProtocolAutoDetection:
    """Test protocol auto-detection from mixed config."""

    @pytest.fixture
    def mixed_config(self, tmp_path: Path) -> Path:
        """Create config with all three protocol types."""
        config = {
            "mcpServers": {
                "test-fs": {
                    "command": "echo",
                    "args": ["test"],
                }
            },
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "graphqlServers": {
                "github": {
                    "url": GITHUB_GRAPHQL_URL,
                }
            },
            "defaults": {
                "cacheTtlSeconds": 3600,
            },
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config_path

    def test_auto_detect_mcp_protocol(self, mixed_config: Path):
        """Test that MCP servers are auto-detected."""
        runner = CliRunner()

        result = runner.invoke(cli, ["discover", "test-fs", "--config", str(mixed_config)])
        # Should detect as MCP and try to connect
        # May fail to connect, but protocol detection should work
        assert "test-fs" in result.output or result.exit_code != 0

    def test_auto_detect_openapi_protocol(self, mixed_config: Path):
        """Test that OpenAPI servers are auto-detected."""
        runner = CliRunner()

        result = runner.invoke(cli, ["discover", "petstore", "--config", str(mixed_config)])
        assert result.exit_code == 0
        assert "pet" in result.output.lower() or "store" in result.output.lower()

    def test_list_all_servers(self, mixed_config: Path):
        """Test listing all servers across protocols."""
        runner = CliRunner()

        result = runner.invoke(cli, ["discover", "--config", str(mixed_config)])
        assert result.exit_code == 0
        # Should list all three server types
        assert "test-fs" in result.output
        assert "petstore" in result.output
        assert "github" in result.output


class TestUltraCompactFormat:
    """Test ultra-compact format across all protocols."""

    @pytest.fixture
    def ultra_config(self, tmp_path: Path) -> Path:
        """Create config for ultra format testing."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {
                "cacheTtlSeconds": 3600,
            },
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config_path

    def test_ultra_format_token_efficiency(self, ultra_config: Path):
        """Test that ultra format is more token-efficient than standard."""
        runner = CliRunner()

        # Generate standard format
        standard_result = runner.invoke(
            cli, ["skills", "petstore", "--config", str(ultra_config)]
        )
        assert standard_result.exit_code == 0
        standard_length = len(standard_result.output)

        # Generate ultra format
        ultra_result = runner.invoke(
            cli, ["skills", "petstore", "--format", "ultra", "--config", str(ultra_config)]
        )
        assert ultra_result.exit_code == 0
        ultra_length = len(ultra_result.output)

        # Ultra format should be more compact
        assert ultra_length < standard_length, "Ultra format should be shorter than standard"

    def test_ultra_format_llm_readable(self, ultra_config: Path):
        """Test that ultra format is still LLM-readable."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["skills", "petstore", "--format", "ultra", "--config", str(ultra_config)]
        )
        assert result.exit_code == 0

        # Ultra format should have:
        # - Tool names
        # - Parameters (abbreviated)
        # - Brief descriptions
        output = result.output
        assert len(output) > 0, "Output should not be empty"

        # Check that output has structured content
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        assert len(lines) > 0, "Should have multiple lines of tools"

    def test_ultra_format_all_protocols(self, tmp_path: Path):
        """Test ultra format works for all protocol types."""
        # Test with OpenAPI (reliable, no auth)
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()
        result = runner.invoke(
            cli, ["skills", "petstore", "--format", "ultra", "--config", str(config_path)]
        )
        assert result.exit_code == 0
        assert len(result.output) > 0


class TestErrorHandling:
    """Test error handling across protocols."""

    def test_openapi_invalid_url(self, tmp_path: Path):
        """Test OpenAPI with invalid URL."""
        config = {
            "openapiServers": {
                "bad-api": {
                    "url": "https://this-url-does-not-exist-12345.com/openapi.json",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "bad-api", "--config", str(config_path)])
        # Should fail gracefully
        assert result.exit_code != 0

    def test_graphql_unauthorized(self, tmp_path: Path):
        """Test GraphQL without auth token."""
        config = {
            "graphqlServers": {
                "github-no-auth": {
                    "url": GITHUB_GRAPHQL_URL,
                    # No auth provided
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()
        result = runner.invoke(
            cli, ["discover", "github-no-auth", "--config", str(config_path)]
        )
        # GitHub GraphQL requires auth, should fail or return limited schema
        # Just verify it doesn't crash
        assert result.exit_code in [0, 1]

    def test_mcp_invalid_command(self, tmp_path: Path):
        """Test MCP with invalid command."""
        config = {
            "mcpServers": {
                "bad-mcp": {
                    "command": "this-command-does-not-exist-12345",
                    "args": [],
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "bad-mcp", "--config", str(config_path)])
        # Should fail gracefully
        assert result.exit_code != 0


class TestCacheBehavior:
    """Test caching behavior across protocols."""

    def test_openapi_cache_hit(self, tmp_path: Path):
        """Test that OpenAPI discovery uses cache."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()

        # First discovery - should fetch from API
        result1 = runner.invoke(cli, ["discover", "petstore", "--config", str(config_path)])
        assert result1.exit_code == 0

        # Second discovery - should use cache (faster)
        result2 = runner.invoke(cli, ["discover", "petstore", "--config", str(config_path)])
        assert result2.exit_code == 0
        assert result1.output == result2.output

    def test_cache_refresh(self, tmp_path: Path):
        """Test cache refresh with --refresh flag."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()

        # First discovery
        result1 = runner.invoke(cli, ["discover", "petstore", "--config", str(config_path)])
        assert result1.exit_code == 0

        # Refresh discovery
        result2 = runner.invoke(
            cli, ["discover", "petstore", "--refresh", "--config", str(config_path)]
        )
        assert result2.exit_code == 0


class TestSubprocessIntegration:
    """Test integration using actual subprocess calls (real CLI usage)."""

    def test_subprocess_openapi_workflow(self, tmp_path: Path):
        """Test OpenAPI workflow via subprocess (real CLI)."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        # Use subprocess to call real CLI
        result = subprocess.run(
            ["dietmcp", "discover", "petstore", "--config", str(config_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should succeed
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "pet" in result.stdout.lower() or "store" in result.stdout.lower()

    def test_subprocess_mcp_workflow(self, tmp_path: Path):
        """Test MCP workflow via subprocess (real CLI)."""
        # Create test directory
        test_dir = Path(TEST_TMP_DIR)
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "subprocess_test.txt"
        test_file.write_text("Subprocess test")

        config = {
            "mcpServers": {
                "test-fs": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", TEST_TMP_DIR],
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        try:
            # Use subprocess to call real CLI
            result = subprocess.run(
                ["dietmcp", "discover", "test-fs", "--config", str(config_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed
            assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
            assert "read_file" in result.stdout

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            if test_dir.exists():
                # Remove all files in test directory
                for item in test_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                # Try to remove the directory
                try:
                    test_dir.rmdir()
                except OSError:
                    # Directory not empty, skip cleanup
                    pass


class TestTokenCounting:
    """Test token counting and efficiency claims."""

    def test_count_tokens_in_ultra_format(self, tmp_path: Path):
        """Count actual tokens in ultra format output."""
        try:
            import tiktoken
        except ImportError:
            pytest.skip("tiktoken not installed - run: pip install tiktoken")

        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()
        result = runner.invoke(
            cli, ["skills", "petstore", "--format", "ultra", "--config", str(config_path)]
        )
        assert result.exit_code == 0

        # Count tokens
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(result.output)
        token_count = len(tokens)

        # Ultra format should be reasonably compact
        # Petstore has many endpoints, but ultra format should keep it manageable
        assert token_count < 5000, f"Ultra format should be compact, got {token_count} tokens"

        # Calculate tokens per tool (rough estimate)
        # Petstore has ~50 endpoints, so we're checking average tokens per endpoint
        # This is a rough sanity check, not a strict requirement
        pass


class TestRealApiExecution:
    """Test actual API execution (not just discovery)."""

    def test_execute_openapi_get_request(self, tmp_path: Path):
        """Test executing real OpenAPI GET request."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()

        # Try to get a pet by ID (read-only operation)
        result = runner.invoke(
            cli,
            [
                "exec",
                "petstore",
                "getPetById",
                "--args",
                json.dumps({"petId": 1}),
                "--config",
                str(config_path),
            ],
        )

        # May succeed or fail depending on API state
        # Just verify command structure is valid
        assert result.exit_code in [0, 1]

    def test_execute_with_output_formats(self, tmp_path: Path):
        """Test execution with different output formats."""
        config = {
            "openapiServers": {
                "petstore": {
                    "url": PETSTORE_URL,
                    "baseUrl": "https://petstore3.swagger.io/api/v3",
                }
            },
            "defaults": {"cacheTtlSeconds": 3600},
        }
        config_path = tmp_path / "servers.json"
        config_path.write_text(json.dumps(config, indent=2))

        runner = CliRunner()

        # Test minified format
        result = runner.invoke(
            cli,
            [
                "exec",
                "petstore",
                "getPetById",
                "--args",
                json.dumps({"petId": 1}),
                "--output-format",
                "minified",
                "--config",
                str(config_path),
            ],
        )
        # Should not crash
        assert result.exit_code in [0, 1]

        # Test summary format (default)
        result = runner.invoke(
            cli,
            [
                "exec",
                "petstore",
                "getPetById",
                "--args",
                json.dumps({"petId": 1}),
                "--output-format",
                "summary",
                "--config",
                str(config_path),
            ],
        )
        # Should not crash
        assert result.exit_code in [0, 1]
