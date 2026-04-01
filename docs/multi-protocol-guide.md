# Multi-Protocol Guide

dietmcp provides a unified CLI interface for three major protocols: **MCP**, **OpenAPI**, and **GraphQL**. This guide explains how to configure and use each protocol effectively.

---

## Table of Contents

1. [Protocol Overview](#protocol-overview)
2. [Configuration](#configuration)
3. [MCP Servers](#mcp-servers)
4. [OpenAPI Servers](#openapi-servers)
5. [GraphQL Servers](#graphql-servers)
6. [Common Patterns](#common-patterns)
7. [Migration Guide](#migration-guide)
8. [Troubleshooting](#troubleshooting)

---

## Protocol Overview

| Protocol | Use Case | Tool Generation | Discovery Method |
|----------|----------|-----------------|------------------|
| **MCP** | Model Context Protocol servers | Native `list_tools()` | Server-provided JSON Schema |
| **OpenAPI** | REST APIs | Automatic from OpenAPI spec | Parse OpenAPI JSON/YAML |
| **GraphQL** | GraphQL APIs | Automatic from introspection | GraphQL introspection query |

### Key Benefits

- **Unified CLI syntax** for all protocols: `dietmcp exec <server> <tool> --args '{...}'`
- **Ultra-compact summaries** (13-16 tokens/tool) across all protocols
- **Same output formats** (summary, minified, CSV, TOON) for all protocols
- **Unified caching** (1-hour TTL) for all protocols
- **Auto-detection** — no need to specify protocol when executing

---

## Configuration

All three protocols are configured in a single file (`servers.json`). Run `dietmcp config path` to find your config location.

### Example Configuration

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  },
  "openapiServers": {
    "petstore": {
      "url": "https://petstore.swagger.io/v2/swagger.json",
      "baseUrl": "https://petstore.swagger.io/v2",
      "auth": {
        "header": "Authorization: Bearer ${PETSTORE_API_KEY}"
      }
    }
  },
  "graphqlServers": {
    "github": {
      "url": "https://api.github.com/graphql",
      "auth": {
        "header": "Authorization: Bearer ${GITHUB_TOKEN}"
      }
    }
  },
  "defaults": {
    "cacheTtlSeconds": 3600,
    "outputFormat": "summary",
    "maxResponseSize": 50000
  }
}
```

### Credential Management

All protocols support credential resolution from environment variables:

```bash
# .env file in your project or config directory
GITHUB_TOKEN=ghp_abc123
PETSTORE_API_KEY=sk_xyz789
```

Use `${VAR_NAME}` placeholders in config — dietmcp resolves them at runtime and masks them in error output.

---

## MCP Servers

Model Context Protocol servers communicate via stdio or SSE.

### Stdio (Local Process)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}
```

### SSE (Remote Server)

```json
{
  "mcpServers": {
    "remote-mcp": {
      "url": "https://example.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      }
    }
  }
}
```

### Discovery & Execution

```bash
# Discover tools
dietmcp discover filesystem

# Execute tool
dietmcp exec filesystem read_file --args '{"path": "/tmp/test.txt"}'

# Generate ultra-compact summary
dietmcp skills filesystem --format ultra
```

### Example Output

```
# filesystem (6 tools)

## File Operations
- read_file(path, offset?, limit?) Read file with optional offset/limit
- write_file(path, content) Create or overwrite file
- list_directory(path) List directory contents

Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'
```

---

## OpenAPI Servers

OpenAPI servers automatically generate tools from REST API specifications.

### Configuration

```json
{
  "openapiServers": {
    "petstore": {
      "url": "https://petstore.swagger.io/v2/swagger.json",
      "baseUrl": "https://petstore.swagger.io/v2",
      "auth": {
        "header": "Authorization: Bearer ${PETSTORE_API_KEY}"
      },
      "cacheTtl": 7200
    }
  }
}
```

**Fields:**
- `url` (required): OpenAPI spec URL or file path (JSON/YAML)
- `baseUrl` (optional): Override base URL from spec
- `auth` (optional): Authentication configuration
- `cacheTtl` (optional): Cache TTL in seconds

### Tool Generation

dietmcp automatically generates tools from OpenAPI endpoints:

| OpenAPI | Tool Name | Example |
|---------|-----------|---------|
| `GET /pets` | `getPets` | `dietmcp exec petstore getPets --args '{"limit": 10}'` |
| `GET /pets/{id}` | `getPetById` | `dietmcp exec petstore getPetById --args '{"id": "1"}'` |
| `POST /pets` | `createPet` | `dietmcp exec petstore createPet --args '{"name": "Fluffy", "tag": "cat"}'` |
| `DELETE /pets/{id}` | `deletePet` | `dietmcp exec petstore deletePet --args '{"id": "1"}'` |

### Parameter Mapping

OpenAPI parameters map to tool arguments:

| OpenAPI Parameter In | Tool Argument | Example |
|---------------------|---------------|---------|
| `path` | Required string | `/pets/{id}` → `{"id": "1"}` |
| `query` | Optional string | `?limit=10` → `{"limit": 10}` |
| `header` | Auth header only | Via `auth.header` config |
| `requestBody` | Object | POST body → `{"name": "Fluffy"}` |

### Discovery & Execution

```bash
# Discover tools (parses OpenAPI spec)
dietmcp discover petstore

# Execute tool
dietmcp exec petstore getPetById --args '{"id": "1"}'

# Generate ultra-compact summary
dietmcp skills petstore --format ultra
```

### Example Output

```
# petstore (15 tools)

## Pet Operations
- getPets(limit?) List all pets with optional limit
- getPetById(id) Get pet by ID
- createPet(name, tag?) Create new pet
- deletePet(id) Delete pet by ID

Exec: dietmcp exec petstore <tool> --args '{"key": "value"}'
```

---

## GraphQL Servers

GraphQL servers use native introspection to generate tools from queries and mutations.

### Configuration

```json
{
  "graphqlServers": {
    "github": {
      "url": "https://api.github.com/graphql",
      "auth": {
        "header": "Authorization: Bearer ${GITHUB_TOKEN}"
      },
      "cacheTtl": 1800
    }
  }
}
```

**Fields:**
- `url` (required): GraphQL endpoint URL
- `auth` (optional): Authentication configuration
- `cacheTtl` (optional): Cache TTL in seconds

### Native Introspection

dietmcp uses GraphQL introspection to automatically discover queries and mutations:

```graphql
query IntrospectionQuery {
  __schema {
    queryType { fields { name description args { name type } } }
    mutationType { fields { name description args { name type } } }
  }
}
```

**Advantages over schema-based approach:**
- No manual schema files required
- Always in sync with live API
- Supports APIs that change frequently
- Discovers deprecated fields and descriptions

### Tool Generation

GraphQL queries and mutations become tools:

| GraphQL Field | Tool Name | Example |
|---------------|-----------|---------|
| `query.getRepository` | `getRepository` | `dietmcp exec github getRepository --args '{"owner": "anthropics", "name": "claude-code"}'` |
| `query.searchRepositories` | `searchRepositories` | `dietmcp exec github searchRepositories --args '{"query": "language:python", "first": 10}'` |
| `mutation.addComment` | `addComment` | `dietmcp exec github addComment --args '{"subjectId": "MDA=", "body": "Great work!"}'` |

### Argument Mapping

GraphQL arguments map directly to tool arguments:

```bash
# GraphQL query
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
    name
  }
}

# Becomes tool call
dietmcp exec github getRepository \
  --args '{"owner": "anthropics", "name": "claude-code"}'
```

### Discovery & Execution

```bash
# Discover tools (introspects GraphQL schema)
dietmcp discover github

# Execute tool
dietmcp exec github getRepository \
  --args '{"owner": "anthropics", "name": "claude-code"}'

# Generate ultra-compact summary
dietmcp skills github --format ultra
```

### Example Output

```
# github (42 tools)

## Repository
- getRepository(owner, name) Get repository by owner and name
- searchRepositories(query, first?) Search repositories with filters

## Issues
- getIssue(owner, name, number) Get issue by owner, repo, and number
- createIssue(input) Create new issue

Exec: dietmcp exec github <tool> --args '{"key": "value"}'
```

---

## Common Patterns

### Authentication

All protocols support header-based authentication:

```json
{
  "mcpServers": {
    "api": {
      "url": "https://api.example.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    }
  },
  "openapiServers": {
    "api": {
      "url": "https://api.example.com/openapi.json",
      "auth": {
        "header": "Authorization: Bearer ${API_TOKEN}"
      }
    }
  },
  "graphqlServers": {
    "api": {
      "url": "https://api.example.com/graphql",
      "auth": {
        "header": "Authorization: Bearer ${API_TOKEN}"
      }
    }
  }
}
```

### Cache Configuration

Fine-tune cache TTL per server:

```json
{
  "defaults": {
    "cacheTtlSeconds": 3600
  },
  "mcpServers": {
    "stable-api": {
      "command": "...",
      "cache_ttl": 7200
    },
    "volatile-api": {
      "command": "...",
      "cache_ttl": 300
    }
  },
  "openapiServers": {
    "stable-api": {
      "url": "...",
      "cacheTtl": 7200
    }
  },
  "graphqlServers": {
    "volatile-api": {
      "url": "...",
      "cacheTtl": 600
    }
  }
}
```

### Output Formats

All protocols support the same output formats:

```bash
# Summary (default, LLM-friendly)
dietmcp exec petstore getPets --args '{"limit": 10}'

# Minified JSON (programmatic)
dietmcp exec petstore getPets --args '{}' --output-format minified

# CSV (tabular data)
dietmcp exec github searchRepositories --args '{"query": "python"}' --output-format csv

# TOON (40-60% smaller than JSON)
dietmcp exec github searchRepositories --args '{"query": "python"}' --output-format toon
```

### Skill Generation

Generate ultra-compact summaries for all servers:

```bash
# Single server
dietmcp skills petstore --format ultra

# All servers (all protocols)
dietmcp skills --all --format ultra > /tmp/all_skills.md
```

---

## Migration Guide

### From MCP-Only to Multi-Protocol

If you're already using dietmcp for MCP servers, adding OpenAPI or GraphQL servers is straightforward:

1. **Update config file** — Add `openapiServers` or `graphqlServers` sections
2. **No CLI changes** — Same commands work for all protocols
3. **Same token efficiency** — Ultra-compact format works for all protocols

### Before (MCP-only)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}
```

### After (Multi-protocol)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  },
  "openapiServers": {
    "petstore": {
      "url": "https://petstore.swagger.io/v2/swagger.json"
    }
  },
  "graphqlServers": {
    "github": {
      "url": "https://api.github.com/graphql",
      "auth": {
        "header": "Authorization: Bearer ${GITHUB_TOKEN}"
      }
    }
  }
}
```

### Usage Remains the Same

```bash
# Works for all protocols
dietmcp discover <server>
dietmcp exec <server> <tool> --args '{...}'
dietmcp skills <server> --format ultra
```

---

## Troubleshooting

### Protocol Detection Issues

**Problem:** Server not discovered or executed correctly.

**Solution:** dietmcp auto-detects protocol from config section. Ensure server is in the correct section:

```json
{
  "mcpServers": {
    "filesystem": { ... }      // MCP
  },
  "openapiServers": {
    "petstore": { ... }        // OpenAPI
  },
  "graphqlServers": {
    "github": { ... }          // GraphQL
  }
}
```

### OpenAPI Spec Parsing Errors

**Problem:** Failed to parse OpenAPI spec.

**Solutions:**
- Verify URL is accessible: `curl https://petstore.swagger.io/v2/swagger.json`
- Check spec is valid JSON/YAML
- Use file path if URL has CORS issues: `"url": "/path/to/local/spec.json"`

### GraphQL Introspection Failures

**Problem:** Introspection query failed.

**Solutions:**
- Verify endpoint is accessible: `curl -X POST https://api.github.com/graphql`
- Check authentication is valid
- Some APIs disable introspection — check API documentation

### Auth Header Issues

**Problem:** Authentication failing despite correct credentials.

**Solutions:**
- Ensure `${VAR}` is in `.env` or shell environment
- Check header format: `"Authorization: Bearer ${TOKEN}"` (not `"Authorization: Bearer TOKEN"`)
- MCP SSE servers use `headers`, OpenAPI/GraphQL use `auth.header`

### Cache Issues

**Problem:** Stale tool definitions after API changes.

**Solution:** Force refresh:

```bash
dietmcp discover <server> --refresh
```

### Performance Issues

**Problem:** Slow discovery or execution.

**Solutions:**
- Increase cache TTL for stable APIs
- Use ultra-compact format to reduce token usage
- Redirect large outputs to files: `--output-file /tmp/out.txt`

---

## Examples Directory

See the `examples/` directory for complete working examples:

- `examples/openapi_integration.py` — OpenAPI tool generation
- `examples/graphql_introspection.py` — GraphQL introspection
- `examples/openapi_petstore.py` — Petstore API usage
- `examples/github_graphql.py` — GitHub GraphQL usage
- `examples/multi_protocol_config.json` — Example config with all protocols

---

## Protocol-Specific Docs

- **OpenAPI:** [OpenAPI Generator](./openapi_generator.md)
- **GraphQL:** [GraphQL Introspection](./graphql_introspection.md)
- **Migration:** [Migration Guide](./migration-guide.md)

---

## Summary

| Feature | MCP | OpenAPI | GraphQL |
|---------|-----|---------|---------|
| **Discovery** | `list_tools()` | Parse spec | Introspection |
| **Execution** | `call_tool()` | HTTP request | GraphQL query |
| **Auth** | `env` / `headers` | `auth.header` | `auth.header` |
| **Caching** | ✅ 1-hour TTL | ✅ 1-hour TTL | ✅ 1-hour TTL |
| **Output formats** | 4 | 4 | 4 |
| **Ultra-compact** | ✅ 13-16 tokens/tool | ✅ 13-16 tokens/tool | ✅ 13-16 tokens/tool |

**All protocols share:**
- Unified CLI syntax
- Same output formats
- Ultra-compact summaries
- Credential management
- Cache configuration

Use the protocol that matches your API, and dietmcp handles the rest.
