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
dietmcp skills <server>            # compact skill summary
```

## Options

- `--output-format minified` -- compact JSON output
- `--output-format csv` -- tabular output
- `--output-file /tmp/result.txt` -- redirect large responses to disk
- `--refresh` -- force fresh schema fetch (with discover/skills)

## Error handling

Non-zero exit code means failure. Check `$?` or use `&&` chaining. Error output goes to stderr.

## Example

```bash
# context7: resolve library then query docs
dietmcp exec context7 resolve-library-id --args '{"libraryName": "react"}'
dietmcp exec context7 query-docs --args '{"libraryId": "/facebook/react", "query": "useEffect cleanup"}'

# large response: redirect to file, read selectively
dietmcp exec filesystem read_file \
  --args '{"path": "/tmp/big.log"}' \
  --output-file /tmp/result.txt
```
