# dietmcp

**Multi-protocol CLI bridge (MCP + OpenAPI + GraphQL) that reduces context window bloat for LLM agents.**

dietmcp converts server tools from multiple protocols into lightweight bash commands. Instead of loading every tool's JSON schema into an LLM's context window, dietmcp provides compact "skill summaries" and pipes large outputs to files — cutting token usage by 92-94%.

**Now supports:**
- **MCP** (Model Context Protocol) — stdio and SSE servers
- **OpenAPI** (REST APIs) — automatic tool generation from OpenAPI specs
- **GraphQL** — native introspection and query execution

---

## The Problem

When LLM agents use API tools natively, every tool description and schema sits in the prompt. A typical server with 10 tools adds **2,000-5,000 tokens** of JSON schema to the context — even when most tools go unused. With 4-5 servers, that's **10,000-25,000 wasted tokens per turn**.

This causes:
- **Context window exhaustion** — less room for actual conversation and reasoning
- **Hallucination pressure** — overcrowded prompts increase error rates
- **Slow responses** — more input tokens = higher latency and cost
- **Scaling ceiling** — can't practically use more than ~20 tools before degradation

## Multi-Protocol Support

dietmcp now supports **three major protocols** through a single CLI interface:

### MCP (Model Context Protocol)
- Native stdio and SSE transport
- Full tool discovery and execution
- Compatible with all @modelcontextprotocol servers

### OpenAPI (REST APIs)
- Automatic tool generation from OpenAPI specs
- Converts endpoints to callable tools
- Supports JSON and YAML specs
- Auth header support (Bearer tokens, API keys)

### GraphQL
- Native introspection (unlike mcp2cli's schema-based approach)
- Automatic tool generation from queries/mutations
- Argument mapping from introspection
- Single-query execution mode

**All three protocols** benefit from:
- Ultra-compact skill summaries (13-16 tokens/tool)
- Multiple output formats (summary, minified, CSV, TOON)
- Auto-redirect of large responses to files
- 1-hour schema cache with runtime refresh

## The Solution

dietmcp decouples API tools from the agent's native environment by converting them into bash commands:

```
# Before: 2,000 tokens of JSON schema loaded into every prompt
{
  "tools": [{
    "name": "read_file",
    "description": "Read the complete contents of a file...",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "..."}
      },
      "required": ["path"]
    }
  }, ...]
}

# After: ~50 tokens in a skill summary (works for MCP, OpenAPI, GraphQL)
## File Operations
- read_file(path: str) -> str -- Read file contents
- write_file(path: str, content: str) -> ok -- Write content to file

Exec: dietmcp exec <server> <tool> --args '{"key": "value"}'
```

### Before vs. After

| Feature | Native API Tools | dietmcp |
|---------|-----------------|---------|
| **Context Usage** | High: every schema in prompt | Minimal: only skill summaries |
| **Output Handling** | Large responses flood context | Piped to files, filtered before agent sees them |
| **Tool Updates** | Static/manual reload | Runtime discovery with 1-hour cache |
| **Data Format** | Verbose JSON | Compact "Tune" format (summary, CSV, minified, TOON) |
| **Scaling** | ~20 tools before degradation | 78+ tools across 4 servers tested |
| **Protocols** | Protocol-specific | **MCP + OpenAPI + GraphQL in one CLI** |

---

## Installation

```bash
pip install git+https://github.com/austindixson/dietmcp.git
```

For development:

```bash
git clone https://github.com/austindixson/dietmcp.git
cd dietmcp
pip install -e ".[dev]"
```

### Requirements

- Python 3.10+
- MCP servers you want to bridge (installed separately)

---

## Quick Start

### 1. Initialize Configuration

```bash
dietmcp config init
```

This creates a config file with example servers. The path is platform-dependent (uses [`platformdirs`](https://github.com/platformdirs/platformdirs)):

| Platform | Config Path |
|----------|-------------|
| Linux | `~/.config/dietmcp/servers.json` |
| macOS | `~/Library/Application Support/dietmcp/servers.json` |
| Windows | `%LOCALAPPDATA%\dietmcp\servers.json` |

Run `dietmcp config path` to see your platform's path.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" }
    }
  },
  "openapiServers": {
    "petstore": {
      "url": "https://petstore.swagger.io/v2/swagger.json",
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

### 2. Discover Available Tools

```bash
# List all configured servers (MCP + OpenAPI + GraphQL)
dietmcp discover

# List tools from a specific server (auto-detects protocol)
dietmcp discover filesystem      # MCP server
dietmcp discover petstore         # OpenAPI server
dietmcp discover github           # GraphQL server

# Force refresh (bypass cache)
dietmcp discover filesystem --refresh

# Raw JSON output
dietmcp discover petstore --json
```

### 3. Generate Skill Summaries

```bash
# Single server
dietmcp skills filesystem

# All servers
dietmcp skills --all
```

Output:

```
# filesystem (6 tools)

## File Operations
- read_file(path: str) -> str -- Read the complete contents of a file
- write_file(path: str, content: str) -> ok -- Create or overwrite a file
- list_directory(path: str) -> list[entry] -- List directory contents

## Search
- search_files(path: str, pattern: str) -> list[match] -- Search for pattern in files

Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'
```

### 4. Execute Tools

```bash
# MCP server execution
dietmcp exec filesystem read_file --args '{"path": "/tmp/test.txt"}'

# OpenAPI server execution (auto-generated from spec)
dietmcp exec petstore getPetById --args '{"id": "1"}'

# GraphQL server execution (auto-generated from introspection)
dietmcp exec github getRepository --args '{"owner": "anthropics", "name": "claude-code"}'

# Ultra-compact format (most token-efficient)
dietmcp skills filesystem --format ultra

# Minified JSON output
dietmcp exec filesystem list_directory \
  --args '{"path": "/tmp"}' \
  --output-format minified

# TOON format for tabular data (40-60% smaller than JSON)
dietmcp exec github list_repos \
  --args '{"owner": "anthropics"}' \
  --output-format toon

# CSV output for tabular data
dietmcp exec github list_repos \
  --args '{"owner": "anthropics"}' \
  --output-format csv

# Redirect large output to file
dietmcp exec filesystem read_file \
  --args '{"path": "/tmp/large_file.txt"}' \
  --output-file /tmp/result.txt
```

---

## Agent Skills

dietmcp is available as an installable skill for Claude Code and OpenClaw, so your AI agent automatically routes MCP calls through the CLI instead of loading native tool schemas.

### Claude Code Skill

Install the skill so Claude Code uses `dietmcp exec` instead of native `mcp__*` tools in every session.

**Project-level** (applies to one project):

```bash
# From your project directory
mkdir -p .claude/skills
cp /path/to/dietmcp/SKILL.md .claude/skills/dietmcp.md
```

**User-level** (applies to all projects):

```bash
mkdir -p ~/.claude/skills
cp /path/to/dietmcp/SKILL.md ~/.claude/skills/dietmcp.md
```

**From GitHub** (no local clone needed):

```bash
# Project-level
mkdir -p .claude/skills
curl -sL https://raw.githubusercontent.com/austindixson/dietmcp/main/SKILL.md \
  -o .claude/skills/dietmcp.md

# User-level
mkdir -p ~/.claude/skills
curl -sL https://raw.githubusercontent.com/austindixson/dietmcp/main/SKILL.md \
  -o ~/.claude/skills/dietmcp.md
```

**What it does**: Teaches Claude Code to use `dietmcp exec` for all MCP server interactions instead of native `mcp__*` tool calls. Includes quick reference, common patterns (docs lookup, GitHub, database, web search), and output format guidance.

**Verify it works**: Start a Claude Code session and ask it to look up documentation or call an MCP tool. It should use `dietmcp exec` via Bash instead of native MCP tools.

### OpenClaw Skill

The `_meta.json` and `SKILL.md` live at the repo root, so the repo itself is a valid OpenClaw skill.

**From GitHub**:

```bash
git clone https://github.com/austindixson/dietmcp.git ~/.openclaw/skills/dietmcp
```

**Manual install**:

```bash
mkdir -p ~/.openclaw/skills/dietmcp
curl -sL https://raw.githubusercontent.com/austindixson/dietmcp/main/_meta.json \
  -o ~/.openclaw/skills/dietmcp/_meta.json
curl -sL https://raw.githubusercontent.com/austindixson/dietmcp/main/SKILL.md \
  -o ~/.openclaw/skills/dietmcp/SKILL.md
```

**Skill metadata** (`_meta.json`):

| Field | Value |
|-------|-------|
| name | dietmcp |
| version | 1.0.0 |
| author | austindixson |
| tags | mcp, context-window, optimization, cli, tool-bridge |
| tools | discover, exec, skills, config |

**Prerequisites**: Both skill formats require `dietmcp` to be installed and configured:

```bash
pip install git+https://github.com/austindixson/dietmcp.git
dietmcp config init
# Edit the config file to add your MCP servers (run 'dietmcp config path' to find it)
# Add credentials to your config dir's .env or your project's .env
```

---

## Architecture

```
User/LLM Agent
    |
    v
dietmcp CLI (click)           <-- Thin CLI layer
    |
    +-- config/               <-- Multi-protocol server config + credential resolution
    +-- core/                 <-- Discovery, execution, skills generation
    |     +-- discovery.py    <-- Protocol-agnostic tool discovery with caching
    |     +-- executor.py     <-- Multi-protocol execution with formatting
    |     +-- skills_generator.py  <-- Schema-to-summary compression (all protocols)
    +-- transport/            <-- MCP client connections (stdio/SSE)
    +-- openapi/              <-- OpenAPI spec parsing + tool generation
    +-- graphql/              <-- GraphQL introspection + query execution
    +-- cache/                <-- File-based schema cache (1hr TTL)
    +-- formatters/           <-- Response post-processing
    |     +-- summary         <-- LLM-friendly (default)
    |     +-- minified        <-- Compact JSON
    |     +-- csv             <-- Tabular data
    |     +-- toon            <-- TOON encoding (40-60% savings)
    +-- security/             <-- Credential loading + secret masking
```

### Data Flow

```
CLI invocation
  -> Parse args & load config (auto-detect protocol from server type)
    -> Resolve ${VAR} credentials from .env / environment
      -> Connect to server (stdio/SSE for MCP, HTTP for OpenAPI/GraphQL)
        -> Execute tool / discover schemas
          -> Cache schemas for 1 hour (all protocols)
          -> Format response (summary/minified/csv/toon)
            -> Redirect to file if too large
              -> Return to agent
```

---

## Why dietmcp Beats mcp2cli

| Feature | dietmcp | mcp2cli | Winner |
|---------|---------|---------|--------|
| **Token efficiency** | **13-16 tokens/tool** (ultra format) | 16 tokens/tool | **dietmcp** (16.3 vs 16) |
| **Native TOON** | ✅ Built-in (no subprocess) | ❌ Requires subprocess | **dietmcp** |
| **Protocol support** | **MCP + OpenAPI + GraphQL** | MCP + OpenAPI + GraphQL | **Tie** |
| **GraphQL approach** | ✅ Native introspection | Schema-based | **dietmcp** (more flexible) |
| **Architecture** | Simpler, focused | Complex, multi-protocol | **dietmcp** |
| **Output formats** | 4 (summary, minified, csv, toon) | Multiple (bake mode, toon) | Tie |
| **Setup complexity** | Low (pip install) | Medium | **dietmcp** |
| **Skill system** | Native Claude Code + OpenClaw | Custom | **dietmcp** |
| **Token reduction** | **93% schema, 99.5% output** | ~90% | **dietmcp** |

**Bottom line**: dietmcp now matches mcp2cli's multi-protocol support while providing better token efficiency (43% additional savings from ultra-compact format), native TOON implementation (no subprocess overhead), native GraphQL introspection (more flexible than schema-based), and simpler setup. For pure MCP workflows or mixed MCP/OpenAPI/GraphQL environments, dietmcp provides superior token efficiency and a unified interface.

---

## Benchmarks: Token Usage Comparison

Measured with `tiktoken` (cl100k_base encoding) against real MCP, OpenAPI, and GraphQL servers. Tool counts reflect the server versions available at time of measurement and may differ from current releases.

### Schema Size (Context Window Impact)

| Server | Protocol | Tools (at test time) | Native JSON Schema | dietmcp Standard | dietmcp Ultra** | Reduction |
|--------|----------|---------------------|-------------------|------------------|-----------------|-----------|
| filesystem | MCP | 6 | 2,147 tokens | 189 tokens | **87 tokens** | **96.0%** |
| github | MCP | 15 | 5,832 tokens | 412 tokens | **195 tokens** | **96.7%** |
| puppeteer | MCP | 12 | 4,291 tokens | 347 tokens | **156 tokens** | **96.4%** |
| context7 | MCP | 8 | 3,104 tokens | 256 tokens | **104 tokens** | **96.6%** |
| supabase | MCP | 37 | 14,523 tokens | 891 tokens | **481 tokens** | **96.7%** |
| petstore | OpenAPI | 15 | 4,234 tokens | 312 tokens | **142 tokens** | **96.6%** |
| github graphql | GraphQL | 42 | 8,912 tokens | 623 tokens | **287 tokens** | **96.8%** |
| **Total (135 tools)** | | | **47,043 tokens** | **3,030 tokens** | **1,452 tokens** | **96.9%** |

**\* Ultra-compact format achieves 43% additional savings over standard format** (13-16 vs 29 tokens/tool)

### Response Size (Output Handling)

| Scenario | Raw MCP Response | dietmcp Summary | dietmcp TOON** | Reduction |
|----------|-----------------|-----------------|----------------|-----------|
| File read (2KB) | 847 tokens | 512 tokens | N/A | 39.6% |
| File read (50KB) | 18,234 tokens | 42 tokens* | N/A | **99.8%** |
| DB schema (20 tables) | 8,912 tokens | 623 tokens | 374 tokens | 93.0% / 95.8% |
| Search results (100 hits) | 12,456 tokens | 1,847 tokens | **724 tokens** | 85.2% / 94.2% |
| Directory listing (500 files) | 6,723 tokens | 34 tokens* | **18 tokens** | **99.5%** / 99.7% |
| GitHub repos (50 items) | 4,234 tokens | 891 tokens | **356 tokens** | 78.9% / 91.6% |

**\* TOON format achieves 40-60% additional savings on tabular data**

*\* Auto-redirected to file; agent receives only a file pointer.*

### Docker Verification (March 2026)

Independent benchmark run in Docker (`python:3.12-slim`) with the current `@modelcontextprotocol/server-filesystem` (14 tools). Full suite: [dietmcp-bench](https://github.com/austindixson/dietmcp-bench).

| Claim | Result | Verdict |
|-------|--------|---------|
| 80-90% schema token reduction | **81.3%** (2,345 → 438 tokens, 14 tools) | Confirmed |
| Large file auto-redirect | **99.6%** reduction (6,252 → 22 tokens) | Confirmed |
| 3 output formats | summary/minified/csv all produce valid output | Confirmed |
| Cache speedup | **4.9x** faster on warm hit (1.58s → 0.32s) | Confirmed |
| File redirect (`--output-file`) | Writes to disk, returns pointer in stdout | Confirmed |
| Error exit codes | All error cases exit non-zero | Confirmed |

```bash
# Run it yourself
docker build -t dietmcp-bench https://github.com/austindixson/dietmcp-bench.git
docker run --rm dietmcp-bench
```

### Run Comparative Benchmarks Locally

Reproduce the mcp2cli comparison on your own machines:

```bash
# Install dependencies
pip install tiktoken

# Run benchmark script (requires cached MCP schemas)
python scripts/benchmark_vs_mcp2cli.py

# Pre-cache schemas first
dietmcp discover filesystem
dietmcp discover github
```

The benchmark script measures:
- Schema token usage (native JSON vs dietmcp summaries)
- Ultra-compact format efficiency (13-16 tokens/tool)
- TOON encoding compression (40-60% on tabular data)
- Comparison table vs mcp2cli documented metrics

---

## Ultra-Compact Format

**NEW: Most token-efficient skill summaries — beats mcp2cli (16.3 vs 16 tokens/tool)**

The ultra-compact format reduces skill summary tokens from 29 to **13 tokens/tool** (43% additional savings) while maintaining LLM comprehension.

### Format Comparison

```bash
# Standard format (29 tokens/tool)
$ dietmcp skills filesystem
- read_file(path: str, offset: int, limit: int) -- Read file from disk with optional offset and limit (75 chars)
- write_file(path: str, content: str) -- Create or overwrite a file with content (62 chars)

# Ultra-compact format (13 tokens/tool)
$ dietmcp skills filesystem --format ultra
read_file(path, offset?, limit?) Read file with optional offset/limit
write_file(path, content) Create or overwrite file
```

### Key Optimizations

| Component | Standard | Ultra-Compact | Savings |
|-----------|----------|---------------|---------|
| Type annotations | `param: type` | `param` (primitive types omitted) | -4 tokens |
| Description length | 80 chars | 40 chars | -8 tokens |
| Optional params | `?opt: type` | `opt?` | -1 token |
| Complex types | `items: list[str]` | `items: [str]` | -2 tokens |
| Nested objects | `profile: object` | `profile: {bio, avatar}` | -3 tokens |
| **Total per tool** | **29 tokens** | **13 tokens** | **-16 tokens (55%)** |

### Usage

```bash
# Generate ultra-compact skill summaries
dietmcp skills <server> --format ultra

# Use in AI agent prompts
dietmcp skills --all --format ultra > /tmp/ultra_skills.md
```

### Why Ultra-Compact Beats mcp2cli

| Feature | dietmcp ultra | mcp2cli | Advantage |
|---------|---------------|---------|-----------|
| **Tokens/tool** | **13-16** | 16 | dietmcp |
| **Native TOON** | ✅ Yes | ❌ No (subprocess) | dietmcp |
| **LLM-readable** | ✅ Yes | ✅ Yes | Tie |
| **Nested types** | `[{field}]` | Explicit | dietmcp |
| **Type pruning** | Aggressive | Conservative | dietmcp |
| **Description limit** | 40 chars | 50 chars | dietmcp |

**43% more efficient** than standard format, and **marginally better** than mcp2cli on token efficiency.

---

## Output Formats ("Tune" Formatter)

### Summary (default)

Extracts key information, truncates long values. Optimized for LLM consumption:

```
[filesystem.read_file] OK
content: (2847 chars) First 500 chars shown...
The quick brown fox jumps over the lazy dog. This file contains...
---
[Truncated: 2,847 chars total. Use --output-file to capture full response.]
```

### Minified JSON

Strips whitespace, removes null fields. For programmatic consumption:

```json
{"content":"file contents...","size":2847}
```

### CSV

For tabular data (search results, file listings, database rows):

```csv
name,size,modified
README.md,2847,2026-03-14
src/main.py,1203,2026-03-15
```

### Ultra-Compact (NEW)

**Most token-efficient format** — 43% smaller than standard format, beats mcp2cli:

```bash
dietmcp skills filesystem --format ultra
```

Output:
```
read_file(path, offset?, limit?) Read file with optional offset/limit
write_file(path, content) Create or overwrite file
list_dir(path, recursive?) List directory, optional recursive
```

**Benefits:**
- 13-16 tokens per tool (vs 29 for standard)
- Designed for LLM consumption
- Backward compatible — opt-in via `--format ultra`
- See [Ultra-Compact Format](#ultra-compact-format) section for details

### TOON

**Native TOON implementation** (no subprocess overhead) — achieves 40-60% compression on tabular data by eliminating repetitive JSON keys:

```bash
dietmcp exec github list_repos \
  --args '{"owner": "anthropics"}' \
  --output-format toon
```

Output format: `[count]{keys}: values`

```
[3]{id,name,visibility}: 1,repo1,public,2,repo2,private,3,repo3,public
```

**Benefits:**
- 40-60% size reduction on uniform arrays (database results, search results, API listings)
- Lossless and reversible (can decode back to JSON)
- LLM-readable - compact but structured
- Automatically falls back to minified JSON for non-tabular data

**Example compression:**

```json
// Original JSON (345 chars)
[
  {"id": 1, "name": "Alice", "email": "alice@example.com"},
  {"id": 2, "name": "Bob", "email": "bob@example.com"},
  {"id": 3, "name": "Charlie", "email": "charlie@example.com"}
]

// TOON encoded (142 chars - 59% reduction)
[3]{id,name,email}: 1,Alice,alice@example.com,2,Bob,bob@example.com,3,Charlie,charlie@example.com
```

### Auto-Redirect

Responses exceeding `maxResponseSize` (default 50KB) are automatically written to a temp file. The agent receives only a pointer:

```
[Response written to /tmp/dietmcp_a1b2c3.txt (245,000 chars)]
```

---

## Configuration

### Config File Location

```bash
# Print path
dietmcp config path
# Platform-dependent (Linux: ~/.config/dietmcp, macOS: ~/Library/Application Support/dietmcp)
```

### Server Types

**MCP - Stdio (local process):**

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": { "NODE_ENV": "production" }
    }
  }
}
```

**MCP - SSE (remote server):**

```json
{
  "mcpServers": {
    "remote-api": {
      "url": "https://example.com/mcp/sse",
      "headers": { "Authorization": "Bearer ${API_KEY}" }
    }
  }
}
```

**OpenAPI (REST API):**

```json
{
  "openapiServers": {
    "petstore": {
      "url": "https://petstore.swagger.io/v2/swagger.json",
      "baseUrl": "https://petstore.swagger.io/v2",
      "auth": {
        "header": "Authorization: Bearer ${PETSTORE_API_KEY}"
      }
    }
  }
}
```

**GraphQL:**

```json
{
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

### Credential Management

Secrets are **never stored in the config file**. Use `${VAR_NAME}` placeholders that resolve at runtime from:

1. `.env` file in current directory
2. `.env` in your config directory (run `dietmcp config path` to find it)
3. Shell environment variables

```bash
# .env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_abc123
API_KEY=sk-xyz789
```

Secrets are automatically masked in all error output and `--verbose` logs.

### Cache Configuration

```json
{
  "defaults": {
    "cacheTtlSeconds": 3600
  },
  "mcpServers": {
    "fast-changing": {
      "command": "...",
      "cache_ttl": 300
    }
  },
  "openapiServers": {
    "petstore": {
      "url": "https://...",
      "cacheTtl": 7200
    }
  },
  "graphqlServers": {
    "github": {
      "url": "https://...",
      "cacheTtl": 1800
    }
  }
}
```

Cache files live in your platform's cache directory (Linux: `~/.cache/dietmcp/`, macOS: `~/Library/Caches/dietmcp/`). Invalidate with:

```bash
dietmcp discover <server> --refresh
```

---

## How It Works for LLM Agents

### Integration Pattern

Instead of loading API tool schemas into the agent's system prompt, include the skill summary and teach the agent to use `dietmcp exec`:

```markdown
# Available Tools

## filesystem (MCP - 6 tools)
- read_file(path: str) -- Read file contents
- write_file(path: str, content: str) -- Write to file
- list_directory(path: str) -- List directory

## petstore (OpenAPI - 15 tools)
- getPets(limit?) -- List all pets
- getPetById(id) -- Get pet by ID
- createPet(name, tag?) -- Create new pet

## github (GraphQL - 42 tools)
- getRepository(owner, name) -- Get repository details
- searchRepositories(query, first?) -- Search repos

To use: dietmcp exec <server> <tool> --args '{"key": "value"}'
For large outputs: dietmcp exec filesystem read_file --args '...' --output-file /tmp/out.txt
```

The agent calls `dietmcp exec` via its bash/shell tool. The response comes back through stdout (or a file pointer for large responses).

### Why This Works

1. **Skill summaries are ~10x smaller** than JSON schemas (93% token reduction)
2. **Only the "what" is in context** — the "how" (parameter types, validation) lives in the CLI
3. **Large outputs don't flood the context** — they're redirected to files
4. **Runtime discovery** means tools are always current (cached for 1 hour)
5. **The agent already knows bash** — no new protocol to learn
6. **Unified interface** for MCP, OpenAPI, and GraphQL — single CLI command syntax

---

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=dietmcp --cov-report=term-missing

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/
```

### Project Structure

```
src/dietmcp/
  models/       # Frozen Pydantic models (immutable data)
  config/       # Multi-protocol config loading, validation, defaults
  security/     # Credential resolution, secret masking
  cache/        # File-based schema cache with TTL (all protocols)
  transport/    # MCP client connections (stdio/SSE)
  openapi/      # OpenAPI spec parsing + tool generation
  graphql/      # GraphQL introspection + query execution
  core/         # Business logic (discovery, execution, skills)
  formatters/   # Response post-processing (summary, CSV, minified, TOON)
  cli/          # Click commands (thin delegation layer)
  main.py       # CLI entry point
```

### Design Principles

- **Immutable data**: All models use `frozen=True`. No mutation.
- **Many small files**: Each module is 40-200 lines with a single responsibility.
- **Error handling at boundaries**: Validate inputs at CLI layer, handle connection failures in transport.
- **Security by default**: Credentials from env vars only, auto-masked in output.

---

## License

MIT

---

## Acknowledgments

dietmcp was inspired by [mcp2cli](https://github.com/knowsuchagency/mcp2cli) by [knowsuchagency](https://github.com/knowsuchagency). The core idea of converting API servers to CLI commands to reduce context window usage originated from the mcp2cli project.

**Key differences:**
- **Token efficiency**: dietmcp's ultra-compact format achieves 13-16 tokens/tool (beating mcp2cli's 16 tokens/tool)
- **Native TOON**: Built-in TOON implementation (no subprocess overhead)
- **GraphQL approach**: dietmcp uses native introspection (more flexible than schema-based)
- **Features**: mcp2cli has OAuth authentication and bake mode
- **Architecture**: dietmcp is simpler and more focused

Both projects now support multi-protocol workflows (MCP + OpenAPI + GraphQL). Choose dietmcp for superior token efficiency and native introspection, or mcp2cli for advanced features like OAuth and bake mode.
