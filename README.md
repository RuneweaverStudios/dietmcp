# dietmcp

**MCP-to-CLI bridge that reduces context window bloat for LLM agents.**

dietmcp converts Model Context Protocol (MCP) server tools into lightweight bash commands. Instead of loading every tool's JSON schema into an LLM's context window, dietmcp provides compact "skill summaries" and pipes large outputs to files — cutting token usage by 80-90%.

---

## The Problem

When LLM agents use MCP tools natively, every tool description and schema sits in the prompt. A typical MCP server with 10 tools adds **2,000-5,000 tokens** of JSON schema to the context — even when most tools go unused. With 4-5 servers, that's **10,000-25,000 wasted tokens per turn**.

This causes:
- **Context window exhaustion** — less room for actual conversation and reasoning
- **Hallucination pressure** — overcrowded prompts increase error rates
- **Slow responses** — more input tokens = higher latency and cost
- **Scaling ceiling** — can't practically use more than ~20 tools before degradation

## The Solution

dietmcp decouples MCP tools from the agent's native environment by converting them into bash commands:

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

# After: ~50 tokens in a skill summary
## File Operations
- read_file(path: str) -> str -- Read file contents
- write_file(path: str, content: str) -> ok -- Write content to file

Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'
```

### Before vs. After

| Feature | Native MCP | dietmcp |
|---------|-----------|---------|
| **Context Usage** | High: every schema in prompt | Minimal: only skill summaries |
| **Output Handling** | Large responses flood context | Piped to files, filtered before agent sees them |
| **Tool Updates** | Static/manual reload | Runtime discovery with 1-hour cache |
| **Data Format** | Verbose JSON | Compact "Tune" format (summary, CSV, minified) |
| **Scaling** | ~20 tools before degradation | 78+ tools across 4 servers tested |

---

## Installation

```bash
pip install dietmcp
```

Or for development:

```bash
git clone https://github.com/RuneweaverStudios/dietmcp.git
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
  "defaults": {
    "cacheTtlSeconds": 3600,
    "outputFormat": "summary",
    "maxResponseSize": 50000
  }
}
```

### 2. Discover Available Tools

```bash
# List all configured servers
dietmcp discover

# List tools from a specific server
dietmcp discover filesystem

# Force refresh (bypass cache)
dietmcp discover filesystem --refresh

# Raw JSON output
dietmcp discover filesystem --json
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
# Basic execution
dietmcp exec filesystem read_file --args '{"path": "/tmp/test.txt"}'

# Minified JSON output
dietmcp exec filesystem list_directory \
  --args '{"path": "/tmp"}' \
  --output-format minified

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
curl -sL https://raw.githubusercontent.com/RuneweaverStudios/dietmcp/main/SKILL.md \
  -o .claude/skills/dietmcp.md

# User-level
mkdir -p ~/.claude/skills
curl -sL https://raw.githubusercontent.com/RuneweaverStudios/dietmcp/main/SKILL.md \
  -o ~/.claude/skills/dietmcp.md
```

**What it does**: Teaches Claude Code to use `dietmcp exec` for all MCP server interactions instead of native `mcp__*` tool calls. Includes quick reference, common patterns (docs lookup, GitHub, database, web search), and output format guidance.

**Verify it works**: Start a Claude Code session and ask it to look up documentation or call an MCP tool. It should use `dietmcp exec` via Bash instead of native MCP tools.

### OpenClaw Skill

The `_meta.json` and `SKILL.md` live at the repo root, so the repo itself is a valid OpenClaw skill.

**From GitHub**:

```bash
git clone https://github.com/RuneweaverStudios/dietmcp.git ~/.openclaw/skills/dietmcp
```

**Manual install**:

```bash
mkdir -p ~/.openclaw/skills/dietmcp
curl -sL https://raw.githubusercontent.com/RuneweaverStudios/dietmcp/main/_meta.json \
  -o ~/.openclaw/skills/dietmcp/_meta.json
curl -sL https://raw.githubusercontent.com/RuneweaverStudios/dietmcp/main/SKILL.md \
  -o ~/.openclaw/skills/dietmcp/SKILL.md
```

**Skill metadata** (`_meta.json`):

| Field | Value |
|-------|-------|
| name | dietmcp |
| version | 1.0.0 |
| author | RuneweaverStudios |
| tags | mcp, context-window, optimization, cli, tool-bridge |
| tools | discover, exec, skills, config |

**Prerequisites**: Both skill formats require `dietmcp` to be installed and configured:

```bash
pip install dietmcp
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
    +-- config/               <-- Server config + credential resolution
    +-- core/                 <-- Discovery, execution, skills generation
    |     +-- discovery.py    <-- MCP list_tools() with caching
    |     +-- executor.py     <-- MCP call_tool() with formatting
    |     +-- skills_generator.py  <-- Schema-to-summary compression
    +-- transport/            <-- MCP client connections (stdio/SSE)
    +-- cache/                <-- File-based schema cache (1hr TTL)
    +-- formatters/           <-- Response post-processing
    |     +-- summary         <-- LLM-friendly (default)
    |     +-- minified        <-- Compact JSON
    |     +-- csv             <-- Tabular data
    +-- security/             <-- Credential loading + secret masking
```

### Data Flow

```
CLI invocation
  -> Parse args & load config
    -> Resolve ${VAR} credentials from .env / environment
      -> Connect to MCP server (stdio or SSE)
        -> Execute tool / discover schemas
          -> Cache schemas for 1 hour
          -> Format response (summary/minified/csv)
            -> Redirect to file if too large
              -> Return to agent
```

---

## Benchmarks: Token Usage Comparison

Measured with `tiktoken` (cl100k_base encoding) against real MCP servers. Tool counts reflect the server versions available at time of measurement and may differ from current releases.

### Schema Size (Context Window Impact)

| Server | Tools (at test time) | Native JSON Schema | dietmcp Skill Summary | Reduction |
|--------|---------------------|-------------------|----------------------|-----------|
| filesystem | 6 | 2,147 tokens | 189 tokens | **91.2%** |
| github | 15 | 5,832 tokens | 412 tokens | **92.9%** |
| puppeteer | 12 | 4,291 tokens | 347 tokens | **91.9%** |
| context7 | 8 | 3,104 tokens | 256 tokens | **91.8%** |
| supabase | 37 | 14,523 tokens | 891 tokens | **93.9%** |
| **Total (78 tools)** | | **29,897 tokens** | **2,095 tokens** | **93.0%** |

### Response Size (Output Handling)

| Scenario | Raw MCP Response | dietmcp Summary | Reduction |
|----------|-----------------|-----------------|-----------|
| File read (2KB) | 847 tokens | 512 tokens | 39.6% |
| File read (50KB) | 18,234 tokens | 42 tokens* | **99.8%** |
| DB schema (20 tables) | 8,912 tokens | 623 tokens | 93.0% |
| Search results (100 hits) | 12,456 tokens | 1,847 tokens | 85.2% |
| Directory listing (500 files) | 6,723 tokens | 34 tokens* | **99.5%** |

*\* Auto-redirected to file; agent receives only a file pointer.*

### Docker Verification (March 2026)

Independent benchmark run in Docker (`python:3.12-slim`) with the current `@modelcontextprotocol/server-filesystem` (14 tools). Full suite: [dietmcp-bench](https://github.com/RuneweaverStudios/dietmcp-bench).

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
docker build -t dietmcp-bench https://github.com/RuneweaverStudios/dietmcp-bench.git
docker run --rm dietmcp-bench
```

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

**Stdio (local process):**

```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "env": { "NODE_ENV": "production" }
  }
}
```

**SSE (remote server):**

```json
{
  "remote-api": {
    "url": "https://example.com/mcp/sse",
    "headers": { "Authorization": "Bearer ${API_KEY}" }
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

Instead of loading MCP tool schemas into the agent's system prompt, include the skill summary and teach the agent to use `dietmcp exec`:

```markdown
# Available Tools

## filesystem (6 tools)
- read_file(path: str) -- Read file contents
- write_file(path: str, content: str) -- Write to file
- list_directory(path: str) -- List directory

To use: dietmcp exec filesystem <tool> --args '{"path": "/tmp"}'
For large outputs: dietmcp exec filesystem read_file --args '...' --output-file /tmp/out.txt
```

The agent calls `dietmcp exec` via its bash/shell tool. The response comes back through stdout (or a file pointer for large responses).

### Why This Works

1. **Skill summaries are ~10x smaller** than JSON schemas (93% token reduction)
2. **Only the "what" is in context** — the "how" (parameter types, validation) lives in the CLI
3. **Large outputs don't flood the context** — they're redirected to files
4. **Runtime discovery** means tools are always current (cached for 1 hour)
5. **The agent already knows bash** — no new protocol to learn

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
  config/       # Config loading, validation, defaults
  security/     # Credential resolution, secret masking
  cache/        # File-based schema cache with TTL
  transport/    # MCP client connections (stdio/SSE)
  core/         # Business logic (discovery, execution, skills)
  formatters/   # Response post-processing (summary, CSV, minified)
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
