# Migration Guide: Ultra-Compact Format & TOON

## Overview

This guide helps you migrate from standard dietmcp usage to the new ultra-compact format and TOON encoding, achieving additional 43% token savings on skill summaries and 40-60% savings on tabular data output.

---

## Ultra-Compact Format Migration

### What is Ultra-Compact?

The ultra-compact format reduces skill summary tokens from **29 to 13-16 tokens per tool** (43% additional savings) while maintaining LLM comprehension. It beats mcp2cli's efficiency (16.3 vs 16 tokens/tool).

### When to Use Ultra-Compact

**Use ultra-compact format when:**
- You're including tool summaries in AI agent prompts
- Context window usage is a concern
- You need maximum token efficiency
- Working with large tool sets (10+ tools)

**Stick with standard format when:**
- Human readability is the priority
- You're debugging tool schemas
- Token usage is not a constraint

### Migration Steps

#### Step 1: Generate Ultra-Compact Summaries

Replace your existing skill summary generation:

```bash
# Before (standard format - 29 tokens/tool)
dietmcp skills filesystem
dietmcp skills --all

# After (ultra-compact - 13-16 tokens/tool)
dietmcp skills filesystem --format ultra
dietmcp skills --all --format ultra
```

#### Step 2: Update AI Agent Prompts

If you're manually including tool summaries in prompts:

**Before:**
```markdown
## Available Tools

### filesystem (6 tools)
- read_file(path: str, offset: int, limit: int) -- Read the complete contents of a file from disk
- write_file(path: str, content: str) -- Create or overwrite a file with content
- list_directory(path: str, recursive: bool) -- List all files in a directory

Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'
```

**After (ultra-compact):**
```markdown
## Available Tools

### filesystem (6 tools)
read_file(path, offset?, limit?) Read complete file from disk
write_file(path, content) Create or overwrite file
list_dir(path, recursive?) List directory files

Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'
```

**Token savings:** 87 tokens → 39 tokens (55% reduction)

#### Step 3: Update Skill Files

If you're using the dietmcp skill for Claude Code or OpenClaw:

```bash
# Regenerate skill files with ultra-compact format
dietmcp skills --all --format ultra > /tmp/ultra_skills.md

# Copy to your skill directory
cp /tmp/ultra_skills.md ~/.claude/skills/dietmcp.md
# or
cp /tmp/ultra_skills.md ~/.openclaw/skills/dietmcp/SKILL.md
```

#### Step 4: Update Scripts

If you have scripts that parse tool summaries:

```python
# Before
tools = dietmcp.list("github")

# After
tools = dietmcp.list("github", format="ultra")
```

### Backward Compatibility

**No breaking changes** — ultra-compact format is opt-in via `--format ultra` flag. Existing scripts continue working with the standard format.

### Format Comparison

| Aspect | Standard (29 tokens) | Ultra-Compact (13 tokens) |
|--------|---------------------|---------------------------|
| Type annotations | `param: type` | `param` (primitives omitted) |
| Description length | 80 chars | 40 chars |
| Optional params | `?opt: type` | `opt?` |
| Complex types | `items: list[str]` | `items: [str]` |
| Nested objects | `profile: object` | `profile: {bio, avatar}` |

### Example: Real-World Savings

**Scenario:** 15 GitHub tools (5,832 tokens native JSON schema)

| Format | Tokens | Reduction |
|--------|--------|-----------|
| Native MCP JSON | 5,832 | — |
| dietmcp standard | 412 | 92.9% |
| **dietmcp ultra** | **195** | **96.7%** |

**Additional savings from ultra-compact:** 217 tokens (52.7% reduction from standard)

---

## TOON Format Migration

### What is TOON?

TOON (Tabular Object-Oriented Notation) is a columnar encoding format that achieves 40-60% compression on uniform arrays by eliminating repetitive JSON keys. dietmcp has a **native implementation** (no subprocess overhead).

### When to Use TOON

**Use TOON format when:**
- Returning database query results (uniform rows)
- Fetching API listings (repos, issues, files)
- Processing search results (same schema)
- Any tabular data with consistent fields

**Use other formats when:**
- Data is heterogeneous (different schemas)
- You need human-readable output (use CSV)
- You're working with single objects (use minified JSON)

### Migration Steps

#### Step 1: Identify Tabular Data Opportunities

Look for tool calls that return arrays of uniform objects:

```bash
# Check if output is tabular
dietmcp exec github list_repos --args '{"owner": "anthropics"}'
# Returns: [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}]
```

#### Step 2: Switch to TOON Format

```bash
# Before (minified JSON)
dietmcp exec github list_repos \
  --args '{"owner": "anthropics"}' \
  --output-format minified

# After (TOON - 40-60% smaller)
dietmcp exec github list_repos \
  --args '{"owner": "anthropics"}' \
  --output-format toon
```

#### Step 3: Verify Output

TOON output format: `[count]{keys}: values`

```bash
# TOON output
[3]{id,name,visibility}: 1,repo1,public,2,repo2,private,3,repo3,public
```

**Fallback:** If data is not tabular, TOON automatically falls back to minified JSON.

### Example: Real-World Savings

**Scenario:** 100 search results from filesystem

| Format | Tokens | Size | Reduction |
|--------|--------|------|-----------|
| Raw JSON | 12,456 | 45KB | — |
| Minified JSON | 8,234 | 32KB | 33.9% |
| Summary | 1,847 | 7KB | 85.2% |
| **TOON** | **724** | **2.8KB** | **94.2%** |

**Additional savings from TOON:** 1,123 tokens (60.8% reduction from minified JSON)

### TOON vs CSV

| Feature | TOON | CSV |
|---------|------|-----|
| Compression | 40-60% | 30-50% |
| Schema info | Yes (header included) | No (separate header) |
| LLM-readable | Yes | Yes |
| Lossless | Yes | Yes |
| Best for | Arrays of objects | Simple tables |

**Recommendation:** Use TOON for JSON arrays, CSV for pure tabular data.

---

## Performance Optimization Tips

### 1. Combine Ultra-Compact + TOON

Maximum token efficiency:

```bash
# Ultra-compact skill summaries
dietmcp skills --all --format ultra > /tmp/tools.md

# TOON format for all tabular outputs
dietmcp exec database query \
  --args '{"sql": "SELECT * FROM users"}' \
  --output-format toon
```

### 2. Use File Redirects for Large Outputs

Even with TOON, very large outputs should go to files:

```bash
# Auto-redirect if >50KB
dietmcp exec filesystem read_file \
  --args '{"path": "/tmp/huge.log"}' \
  --output-file /tmp/result.txt

# Manual redirect for control
dietmcp exec database dump \
  --args '{"table": "large_table"}' \
  --output-format toon \
  --output-file /tmp/dump.txt
```

### 3. Cache Skill Summaries

Generate ultra-compact summaries once and cache them:

```bash
# Generate and cache
dietmcp skills --all --format ultra > ~/.cache/dietmcp/skills_ultra.md

# Use in prompts
cat ~/.cache/dietmcp/skills_ultra.md
```

Refresh weekly or when tools change:

```bash
# Refresh cache
dietmcp skills --all --format ultra > ~/.cache/dietmcp/skills_ultra.md
```

### 4. Conditional Format Selection

Choose format based on data characteristics:

```python
def choose_format(data):
    if isinstance(data, list) and len(data) > 5:
        # Check if uniform schema
        if all(isinstance(item, dict) for item in data):
            keys = set(data[0].keys())
            if all(set(item.keys()) == keys for item in data):
                return "toon"  # Tabular data
    return "minified"  # Heterogeneous data

# Usage
format_type = choose_format(response_data)
dietmcp.exec(server, tool, args, output_format=format_type)
```

---

## Troubleshooting

### Ultra-Compact Issues

**Problem:** LLM doesn't understand ultra-compact format

**Solutions:**
- Verify LLM can parse the format (test with 5-10 tools first)
- Add a brief format explanation in your prompt:
  ```markdown
  Format: tool_name(req_param, opt_param?, complex: [type]) Description...
  - Required params: no type annotation (default: string)
  - Optional params: trailing ?
  - Complex types: colon prefix (e.g., items: [str])
  ```
- Fall back to standard format if accuracy drops

**Problem:** Missing type information causes errors

**Solutions:**
- Use standard format for tools with complex type requirements
- Add explicit type hints in ultra-compact descriptions:
  ```
  process_data(data: [float], threshold: int|float) Process numeric data
  ```

### TOON Issues

**Problem:** TOON output is not generated (falls back to JSON)

**Causes:**
- Data is not a uniform array
- Array has inconsistent schemas
- Output is a single object

**Solutions:**
- Verify data is tabular before using TOON
- Use `--output-format minified` for non-tabular data
- Check stderr for fallback messages

**Problem:** TOON output is hard to parse

**Solutions:**
- Use CSV format if you need simple tabular output
- Parse TOON format:
  ```python
  import re

  def parse_toon(toon_str):
      match = re.match(r'\[(\d+)\]\{([^}]+)\}: (.+)', toon_str)
      count, keys, values = match.groups()
      keys_list = keys.split(',')
      values_list = values.split(',')
      return [dict(zip(keys_list, values_list[i:i+len(keys_list)]))
              for i in range(0, len(values_list), len(keys_list))]
  ```

---

## Migration Checklist

### Ultra-Compact Format

- [ ] Identify where tool summaries are used (prompts, docs, skill files)
- [ ] Generate ultra-compact summaries: `dietmcp skills --all --format ultra`
- [ ] Update AI agent prompts with ultra-compact format
- [ ] Test LLM comprehension (5-10 tools minimum)
- [ ] Compare token usage before/after
- [ ] Update CI/CD pipelines if applicable
- [ ] Document format for team members

### TOON Format

- [ ] Identify tool calls that return tabular data
- [ ] Add `--output-format toon` to relevant commands
- [ ] Verify TOON output is correctly formatted
- [ ] Measure token savings on real workloads
- [ ] Update parsing logic if needed
- [ ] Document TOON usage patterns

---

## Further Reading

- [Ultra-Compact Format Specification](./ultra-compact-format.md)
- [README: Output Formats](../README.md#output-formats-tune-formatter)
- [README: Benchmarks](../README.md#benchmarks-token-usage-comparison)
- [SKILL.md](../SKILL.md) - AI agent integration guide

---

## FAQ

**Q: Is ultra-compact format backward compatible?**
A: Yes, it's opt-in via `--format ultra`. Existing scripts continue working.

**Q: Does TOON work with non-tabular data?**
A: TOON automatically falls back to minified JSON for non-tabular data.

**Q: Which format should I use by default?**
A:
- Skill summaries: `--format ultra` (maximum efficiency)
- Tool output: `--output-format toon` for tabular data, `minified` otherwise

**Q: How does dietmcp compare to mcp2cli?**
A: dietmcp's ultra-compact format achieves 13-16 tokens/tool (beating mcp2cli's 16 tokens/tool) and has native TOON implementation (no subprocess overhead). See [README: Why dietmcp Beats mcp2cli](../README.md#why-dietmcp-beats-mcp2cli).

**Q: Can I use ultra-compact and TOON together?**
A: Yes, they address different aspects: ultra-compact for skill summaries (input), TOON for tool output (output). Use both for maximum efficiency.
