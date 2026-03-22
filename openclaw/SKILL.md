# dietmcp: MCP-via-CLI Bridge

Route ALL MCP server interactions through `dietmcp exec` via the Bash tool. NEVER use native `mcp__*` tool calls directly. This reduces context window usage by 90%+ by replacing verbose JSON schemas with compact CLI calls.

## Why

Native MCP tools load 2,000-5,000 tokens of JSON schema per server into the context window on every call. With multiple servers, that's 10,000-25,000 wasted tokens per turn. dietmcp compresses tool schemas into ~200-token skill summaries and pipes large outputs to files, keeping the context lean.

## Quick Reference

```bash
# List configured servers
dietmcp discover

# See tools on a server
dietmcp discover <server>

# Generate compact skill summaries
dietmcp skills <server>
dietmcp skills --all

# Execute a tool
dietmcp exec <server> <tool> --args '{"key": "value"}'

# Execute with output format
dietmcp exec <server> <tool> --args '{"key": "value"}' --output-format minified
dietmcp exec <server> <tool> --args '{"key": "value"}' --output-format csv

# Redirect large output to file
dietmcp exec <server> <tool> --args '{"key": "value"}' --output-file /tmp/result.txt

# Force refresh cached schemas
dietmcp discover <server> --refresh

# View/manage config
dietmcp config show
dietmcp config path
```

## Workflow

1. **Identify the server** -- Check which dietmcp server handles the task
2. **Discover tools if needed** -- Run `dietmcp discover <server>` to see available tools and their parameters
3. **Execute via CLI** -- Use `dietmcp exec <server> <tool> --args '<json>'` via the Bash tool
4. **Handle large output** -- Use `--output-file` for responses that might be large, then read the file selectively

## Common Patterns

### Documentation Lookup (context7)

```bash
# Resolve library ID first
dietmcp exec context7 resolve-library-id --args '{"libraryName": "react"}'

# Then query docs with the resolved ID
dietmcp exec context7 query-docs --args '{"libraryId": "/facebook/react", "query": "useEffect cleanup"}'
```

Fetch docs when:
- Starting a new feature or touching unfamiliar APIs
- Adding or upgrading a dependency
- Debugging unexpected library behavior

### GitHub Operations

```bash
dietmcp exec github search_repositories --args '{"query": "MCP server python"}'
dietmcp exec github get_file_contents --args '{"owner": "org", "repo": "repo", "path": "src/main.py"}'
```

### Database Operations

```bash
dietmcp exec supabase list_tables --args '{}'
dietmcp exec supabase execute_sql --args '{"query": "SELECT * FROM users LIMIT 10"}'
```

### Web Search / Fetch

```bash
dietmcp exec brave-search brave_web_search --args '{"query": "openrouter api pricing 2026"}'
dietmcp exec fetch fetch --args '{"url": "https://api.example.com/data"}'
```

## Output Formats

| Format | Use When | Flag |
|--------|----------|------|
| summary (default) | General tool output, LLM consumption | _(none)_ |
| minified | Programmatic/structured data | `--output-format minified` |
| csv | Tabular data (lists, search results) | `--output-format csv` |
| file redirect | Large responses (>50KB auto-redirects) | `--output-file /path` |

## Key Principles

- Prefer `dietmcp exec` over native `mcp__*` tool calls -- every native call loads thousands of tokens of JSON schema into your context window, and those tokens add up fast across a session. Routing through the CLI keeps the window clean for reasoning.
- When you're unsure which tools a server offers, `dietmcp discover <server>` shows them without the schema bloat.
- For responses that might be large (file reads, database dumps, search results with many hits), use `--output-file` so the content goes to disk instead of flooding your context. You can then read just the parts you need.
- Cached schemas last 1 hour. If tools seem out of date, `--refresh` forces a fresh fetch.
- Arguments are always JSON: `--args '{"key": "value"}'`
