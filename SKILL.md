---
name: dietmcp
description: MCP-via-CLI bridge. Use instead of native mcp__* tool calls to reduce context window usage.
---

# dietmcp

Route MCP server calls through `dietmcp exec` via Bash instead of native `mcp__*` tools.

## Syntax

```bash
dietmcp exec <server> <tool> --args '{"key": "value"}'
dietmcp discover <server>          # list tools on a server
dietmcp discover                   # list all servers
```

## Options

- `--output-format minified` -- compact JSON output
- `--output-format csv` -- tabular output
- `--output-file /tmp/result.txt` -- redirect large responses to disk
- `--refresh` -- force fresh schema fetch (with discover)

## Example

```bash
# context7: resolve library then query docs
dietmcp exec context7 resolve-library-id --args '{"libraryName": "react"}'
dietmcp exec context7 query-docs --args '{"libraryId": "/facebook/react", "query": "useEffect cleanup"}'
```
