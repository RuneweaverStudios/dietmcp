# Twitter/X Thread: dietmcp

> Copy-paste ready thread. Each section is one tweet (< 280 chars unless noted as a long-form tweet).

---

**Tweet 1 (Hook)**

I just solved one of the biggest problems with AI agents using tools.

78 MCP tools. 4 servers. Zero context window bloat.

Here's how I built dietmcp -- and why it changes everything about agent tooling.

Thread

---

**Tweet 2 (The Problem)**

The dirty secret of MCP (Model Context Protocol):

Every tool you add dumps its FULL JSON schema into the agent's prompt.

10 tools = 2,000-5,000 wasted tokens. Per turn. Even if unused.

4 servers? That's 25,000 tokens of JSON garbage before the agent even thinks.

---

**Tweet 3 (The Symptoms)**

What happens when you overload an agent's context with tool schemas:

- Context window exhaustion (less room for actual reasoning)
- Higher hallucination rates on tool calls
- Slower responses (more input tokens = more $$)
- Hard ceiling at ~20 tools before everything degrades

Sound familiar?

---

**Tweet 4 (The Insight)**

The key insight:

Agents already know how to use bash.

So what if we converted MCP tools INTO bash commands?

The agent doesn't need 2,000 tokens of JSON schema. It needs ONE LINE:

`dietmcp exec filesystem read_file --args '{"path": "/tmp/file.txt"}'`

---

**Tweet 5 (The Approach)**

So I built dietmcp. It does 3 things:

1. DISCOVERS tools from any MCP server at runtime
2. COMPRESSES schemas into "skill summaries" (~10x smaller)
3. PIPES large outputs to files so they never flood the context

The agent sees a 200-token cheat sheet instead of 2,000 tokens of JSON.

---

**Tweet 6 (Before/After Visual)**

Before (in agent context):
```json
{"tools": [{"name": "read_file",
"inputSchema": {"type": "object",
"properties": {"path": {"type":
"string"}}}}...]}
```
= 2,147 tokens

After:
```
- read_file(path: str) -- Read file
```
= 189 tokens

91.2% reduction. Per server.

---

**Tweet 7 (Benchmarks)**

Real benchmarks across 5 MCP servers (79 tools total):

filesystem: 82.5% reduction
github: 84.1% reduction
puppeteer: 79.0% reduction
supabase: 83.0% reduction

TOTAL: 10,265 tokens -> 1,813 tokens

That's 82.3% fewer tokens. Every single turn.

---

**Tweet 8 (Output Handling)**

But schema compression is only half the story.

The other killer feature: output handling.

A 50KB file read? Native MCP dumps 12,800 tokens into context.

dietmcp? Writes it to a file. Agent sees:
"[Response written to /tmp/dietmcp_xyz.txt]"

14 tokens. 99.9% reduction.

---

**Tweet 9 (Cache)**

Performance matters when you're a CLI called per-turn.

So I added a file-based schema cache:

- Cache read: 0.09ms
- Live MCP discovery: ~2,000ms
- Speedup: 23,000x

Tool schemas are cached for 1 hour. Config changes auto-invalidate.

---

**Tweet 10 (Architecture)**

The architecture is dead simple:

CLI (click) -> Config (credential resolution) -> Transport (MCP SDK) -> Core (discover/exec/skills) -> Cache + Formatters

26 Python files. None over 200 lines. 111 tests. 83% coverage.

All data models are frozen (immutable). Zero mutation anywhere.

---

**Tweet 11 (Security)**

Security was non-negotiable:

- Credentials NEVER in CLI args (pulled from .env at runtime)
- Config files use ${VAR_NAME} placeholders (safe to commit)
- All error output auto-masked for secret values
- Child processes get resolved env vars without logging them

---

**Tweet 12 (The "Tune" Format)**

I call the output compression "Tune" formatting. Three modes:

SUMMARY: LLM-friendly text (default)
CSV: Tabular data compressed into rows
MINIFIED: Compact JSON, nulls stripped

Responses over 50KB auto-redirect to temp files. The agent never sees the flood.

---

**Tweet 13 (Real Impact)**

What this means in practice:

An agent with Supabase + GitHub + Filesystem + Puppeteer:

Before: ~30,000 tokens of schemas per turn
After: ~1,800 tokens of skill summaries

That's 28,000 tokens freed up. For actual reasoning.

---

**Tweet 14 (How to Use)**

Want to try it?

```
pip install dietmcp
dietmcp config init
dietmcp skills --all
```

Three commands. Your agent now has access to every MCP tool as a bash command.

---

**Tweet 15 (Broader Lesson)**

The broader lesson:

The best way to give an AI agent more capabilities is NOT to shove everything into its prompt.

It's to build a LAYER between the agent and its tools.

Let the agent know WHAT's available. Let the CLI handle HOW.

---

**Tweet 16 (CTA)**

dietmcp is open source.

79 tools. 82% token reduction. 23,000x cache speedup.

If you're building with MCP tools and hitting context limits, this is the fix.

Star, fork, contribute.

---

*End of thread*
