# Multi-Protocol Integration Tests

## Overview

This directory contains comprehensive end-to-end integration tests for dietmcp's multi-protocol support, covering MCP, OpenAPI, and GraphQL protocols.

## Test File

- **File**: `test_multi_protocol.py` (797 lines)
- **Tests**: 23 total integration tests
- **Coverage**: Full workflow testing for all three protocols

## Test Categories

### 1. MCP Protocol Tests (`TestMCPProtocol`)
- **test_mcp_full_workflow**: Complete MCP workflow with filesystem server
  - Config → discover → skills → exec
  - Tests read_file, write_file, list_directory operations
  - Verifies ultra-compact format generation

### 2. OpenAPI Protocol Tests (`TestOpenAPIProtocol`)
- **test_openapi_full_workflow**: Complete OpenAPI workflow with Petstore API
- **test_openapi_discover_json_output**: JSON output format verification
- **test_openapi_multiple_endpoints**: Multiple endpoint discovery

**API Used**: https://petstore3.swagger.io/api/v3/openapi.json (no auth required)

### 3. GraphQL Protocol Tests (`TestGraphQLProtocol`)
- **test_graphql_full_workflow**: Complete GraphQL workflow with GitHub API
- **test_graphql_discover_json_output**: JSON output format verification
- **test_graphql_introspection_fields**: Schema introspection testing

**API Used**: https://api.github.com/graphql (requires `GITHUB_TOKEN` env var)

**Note**: These tests are skipped if `GITHUB_TOKEN` is not set.

### 4. Protocol Auto-Detection Tests (`TestProtocolAutoDetection`)
- **test_auto_detect_mcp_protocol**: MCP protocol auto-detection
- **test_auto_detect_openapi_protocol**: OpenAPI protocol auto-detection
- **test_list_all_servers**: Mixed protocol server listing

### 5. Ultra-Compact Format Tests (`TestUltraCompactFormat`)
- **test_ultra_format_token_efficiency**: Token efficiency verification
- **test_ultra_format_llm_readable**: LLM readability verification
- **test_ultra_format_all_protocols**: Cross-protocol ultra format testing

### 6. Error Handling Tests (`TestErrorHandling`)
- **test_openapi_invalid_url**: Invalid URL handling
- **test_graphql_unauthorized**: Unauthorized GraphQL access
- **test_mcp_invalid_command**: Invalid MCP command handling

### 7. Cache Behavior Tests (`TestCacheBehavior`)
- **test_openapi_cache_hit**: Cache hit verification
- **test_cache_refresh**: Cache refresh with --refresh flag

### 8. Subprocess Integration Tests (`TestSubprocessIntegration`)
- **test_subprocess_openapi_workflow**: Real CLI invocation (OpenAPI)
- **test_subprocess_mcp_workflow**: Real CLI invocation (MCP)

### 9. Token Counting Tests (`TestTokenCounting`)
- **test_count_tokens_in_ultra_format**: Actual token counting with tiktoken

**Note**: Skipped if tiktoken is not installed.

### 10. Real API Execution Tests (`TestRealApiExecution`)
- **test_execute_openapi_get_request**: Real GET request execution
- **test_execute_with_output_formats**: Output format testing (minified, summary)

## Requirements

### Required Dependencies
```bash
pip install -e ".[dev]"
```

### Optional Dependencies
```bash
# For token counting tests
pip install tiktoken

# For GraphQL tests
export GITHUB_TOKEN=your_token_here
```

### System Requirements
- **Node.js**: Required for MCP filesystem server tests
- **Python 3.10+**: Required for test execution
- **Internet connection**: Required for OpenAPI and GraphQL API tests

## Running the Tests

### Run All Tests
```bash
pytest tests/integration/test_multi_protocol.py -v
```

### Run Specific Test Class
```bash
# MCP protocol tests
pytest tests/integration/test_multi_protocol.py::TestMCPProtocol -v

# OpenAPI protocol tests
pytest tests/integration/test_multi_protocol.py::TestOpenAPIProtocol -v

# GraphQL protocol tests (requires GITHUB_TOKEN)
pytest tests/integration/test_multi_protocol.py::TestGraphQLProtocol -v
```

### Run Specific Test
```bash
pytest tests/integration/test_multi_protocol.py::TestOpenAPIProtocol::test_openapi_full_workflow -v
```

### Run with Coverage
```bash
pytest tests/integration/test_multi_protocol.py --cov=dietmcp --cov-report=term-missing
```

### Run with Verbose Output
```bash
pytest tests/integration/test_multi_protocol.py -v -s
```

## Test Results

### Current Status (as of last run)
- **Passed**: 20 tests
- **Skipped**: 3 tests (GraphQL tests without GITHUB_TOKEN)
- **Failed**: 0 tests
- **Duration**: ~17 seconds

### Test Breakdown by Protocol
| Protocol | Tests | Status |
|----------|-------|--------|
| MCP | 2 | ✅ Passing |
| OpenAPI | 8 | ✅ Passing |
| GraphQL | 3 | ⏭️ Skipped (no token) |
| Auto-Detection | 3 | ✅ Passing |
| Ultra Format | 3 | ✅ Passing |
| Error Handling | 3 | ✅ Passing |
| Cache | 2 | ✅ Passing |
| Subprocess | 2 | ✅ Passing |
| Token Counting | 1 | ✅ Passing |
| Real Execution | 2 | ✅ Passing |

## API Documentation

### Petstore OpenAPI (Swagger)
- **URL**: https://petstore3.swagger.io/api/v3/openapi.json
- **Base URL**: https://petstore3.swagger.io/api/v3
- **Auth**: None (public demo API)
- **Endpoints**: ~50 endpoints (pets, users, store)

### GitHub GraphQL API
- **URL**: https://api.github.com/graphql
- **Auth**: Bearer token (GitHub Personal Access Token)
- **Setup**: `export GITHUB_TOKEN=ghp_xxxxx`
- **Note**: Tests are skipped if token is not set

### Filesystem MCP Server
- **Package**: @modelcontextprotocol/server-filesystem
- **Install**: `npx -y @modelcontextprotocol/server-filesystem /path/to/dir`
- **Test Directory**: `/private/tmp/dietmcp_test`

## Troubleshooting

### MCP Tests Fail with "Access Denied"
- **Issue**: Path symlink issues on macOS
- **Solution**: Tests use `/private/tmp` instead of `/tmp` to avoid symlink problems

### GraphQL Tests Skipped
- **Issue**: `GITHUB_TOKEN` not set
- **Solution**: `export GITHUB_TOKEN=your_token_here`

### Token Counting Tests Skipped
- **Issue**: `tiktoken` not installed
- **Solution**: `pip install tiktoken`

### OpenAPI Tests Fail
- **Issue**: Petstore API may be down
- **Solution**: Check https://petstore3.swagger.io status

### MCP Tests Fail
- **Issue**: Node.js not installed or npx not available
- **Solution**: Install Node.js from https://nodejs.org/

## Test Structure

### Fixtures
Each test class uses pytest fixtures to set up test configurations:

```python
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
```

### Test Pattern
Tests follow the standard pattern:

1. **Setup**: Create test configuration
2. **Discover**: Call `dietmcp discover <server>`
3. **Skills**: Call `dietmcp skills <server>`
4. **Execute**: Call `dietmcp exec <server> <tool>`
5. **Verify**: Assert results match expectations
6. **Cleanup**: Remove temporary files/directories

## Contributing

When adding new tests:

1. **Use real APIs** where possible (prefer public APIs over mocks)
2. **Document API requirements** in test docstrings
3. **Handle missing dependencies** gracefully (skip tests with clear messages)
4. **Clean up resources** (files, directories, connections)
5. **Test both success and error cases**
6. **Verify protocol auto-detection** works correctly

## Future Enhancements

- [ ] Add REST API protocol tests (if implemented)
- [ ] Add gRPC protocol tests (if implemented)
- [ ] Add performance benchmarking tests
- [ ] Add concurrent request tests
- [ ] Add rate limiting tests
- [ ] Add WebSocket protocol tests (if implemented)
