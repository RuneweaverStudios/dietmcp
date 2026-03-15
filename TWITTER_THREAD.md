I Built a Tool That Lets AI Agents Use 78 MCP Tools Without Blowing Up Their Context Window

I just solved one of the biggest problems with AI agents using tools. 78 MCP tools. 4 servers. Zero context window bloat. Here's how I built dietmcp — and why it changes everything about agent tooling.


The Dirty Secret of MCP

Here's something nobody talks about with the Model Context Protocol: every tool you add dumps its FULL JSON schema into the agent's prompt. Not just the name. The entire schema — types, descriptions, nested objects, enums, all of it.

10 tools? That's 2,000-5,000 wasted tokens. Per turn. Even when the agent doesn't use a single one of them.

Now scale that up. Connect 4 servers — Supabase, GitHub, Puppeteer, something like Context7 — and you're looking at 25,000 tokens of raw JSON sitting in the prompt before the agent even starts thinking.

The consequences are brutal:

Context window exhaustion. Less room for actual conversation and reasoning. Your 200K window suddenly feels like 175K.

Higher hallucination rates. Overcrowded prompts cause agents to fumble tool calls. They start inventing parameter names. They call tools that don't exist.

Slower, more expensive responses. More input tokens means higher latency and higher cost. Every single turn.

A hard ceiling around 20 tools. Beyond that, quality degrades fast. The agent drowns in its own tool definitions.

If you've built anything with MCP tools and hit that wall — this is why.


The Key Insight

I kept staring at this problem and the answer was embarrassingly simple:

Agents already know how to use bash.

So what if we stopped loading MCP tool schemas into the prompt entirely, and instead converted every MCP tool into a bash command?

The agent doesn't need 2,000 tokens of JSON schema to call read_file. It needs one line:

    dietmcp exec filesystem read_file --args '{"path": "/tmp/file.txt"}'

That's it. The agent calls it through its shell tool. The response comes back through stdout. No schema in context. No protocol overhead. Just a bash command.


What I Built

So I built dietmcp. It's a Python CLI that acts as a bridge between LLM agents and MCP servers. It does three things:

1. DISCOVERS tools from any MCP server at runtime — connects, fetches schemas, caches them.
2. COMPRESSES those schemas into "skill summaries" that are roughly 10x smaller than the raw JSON.
3. PIPES large outputs to files so they never flood the agent's context window.

The agent sees a 200-token cheat sheet instead of 2,000 tokens of JSON.

Here's what the compression looks like in practice.

Before (what sits in the agent's context with native MCP):

    {
      "tools": [{
        "name": "read_file",
        "description": "Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to read"}
          },
          "required": ["path"]
        }
      }, ...]
    }

That's 2,147 tokens for just 6 filesystem tools.

After (dietmcp skill summary):

    filesystem (6 tools)

    File Operations
    - read_file(path: str) -- Read file contents
    - write_file(path: str, content: str) -- Write content to file
    - move_file(source: str, destination: str) -- Move or rename files

    Search
    - search_files(path: str, pattern: str, ?regex: bool) -- Search for files matching a pattern

    Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'

That's 189 tokens. 91.2% reduction. For one server.


The Benchmarks

I ran this against 5 real MCP servers with 79 tools total. These are actual token counts, not estimates:

    Server          Tools    Native JSON    Skill Summary    Reduction
    ---------------------------------------------------------------
    filesystem          6    999 tokens     175 tokens       82.5%
    github             15    2,961 tokens   471 tokens       84.1%
    puppeteer          12    1,093 tokens   229 tokens       79.0%
    context7            8    962 tokens     215 tokens       77.7%
    supabase           38    4,250 tokens   723 tokens       83.0%
    ---------------------------------------------------------------
    TOTAL              79    10,265 tokens  1,813 tokens     82.3%

10,265 tokens compressed to 1,813. Every single turn. That's 8,452 tokens freed up for actual reasoning.


Output Handling: The Other Half

Schema compression is only half the story. The other killer feature is what happens with the response.

When an agent reads a 50KB file through native MCP, all 12,800 tokens of that file content get dumped directly into the conversation history. The agent has to "see" every byte, even if it only needed the first 10 lines.

dietmcp handles this differently. Responses over 50KB are automatically written to a temp file. The agent sees:

    [Response written to /tmp/dietmcp_xyz.txt (51,200 chars)]

14 tokens instead of 12,800. That's a 99.9% reduction.

And because it's a CLI, the agent can pipe and filter before it ever "reads" the output:

    dietmcp exec filesystem read_file --args '{"path": "/tmp/big.log"}' --output-file /tmp/result.txt
    grep "ERROR" /tmp/result.txt | head -20

The agent only sees the 20 error lines it actually needs. Not the entire 50KB log.


Performance: The Cache Layer

When you're a CLI that gets called every turn, milliseconds matter. Connecting to an MCP server, spawning the process, initializing the session, and calling list_tools takes about 2 seconds. That's unacceptable for every invocation.

So I built a file-based schema cache with a 1-hour TTL:

    Cache read:          0.09ms
    Live MCP discovery:  ~2,000ms
    Speedup:             23,000x

The cache uses atomic writes (write to temp, then rename) to prevent corruption from concurrent invocations. Cache keys are derived from the server config, so changing the command or args automatically invalidates the cache. No stale data.


The Architecture

The whole thing is 26 Python files. None over 200 lines.

    CLI (click)
      -> Config (load servers.json, resolve credential placeholders)
        -> Transport (MCP SDK — stdio or SSE connections)
          -> Core (discovery, execution, skills generation)
            -> Cache (file-based, 1hr TTL, atomic writes)
            -> Formatters (summary, CSV, minified JSON, file redirect)

Every data model is frozen (immutable Pydantic models). Zero mutation anywhere in the codebase. 111 tests. 83% coverage.

The config format intentionally mirrors claude_desktop_config.json so you can copy server definitions directly:

    {
      "mcpServers": {
        "github": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-github"],
          "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
        }
      }
    }


Security

Security was non-negotiable. When you're bridging an AI agent to tools that touch your filesystem, database, and GitHub repos, you can't cut corners.

Credentials never appear in CLI args. They're pulled from .env files at runtime. No secrets in ps aux output.

Config files use ${VAR_NAME} placeholders. The config is safe to commit to version control.

All error output is auto-masked. If a secret value accidentally appears in a traceback, it gets replaced with *** before it reaches stdout.

Child processes get resolved env vars passed through the MCP SDK's environment injection, never through command-line flags.


The "Tune" Format

I call the output post-processing "Tune" formatting. Three modes depending on what the agent needs:

SUMMARY (default): LLM-friendly text. Truncates long values, adds hints about using --output-file for full content.

CSV: For tabular data — search results, file listings, database rows. Detects tabular structure automatically and renders as CSV.

MINIFIED: Compact JSON with whitespace stripped and null fields removed. For when the agent needs to parse structured data programmatically.

Anything over 50KB auto-redirects to a temp file regardless of format. The agent gets a file pointer, not a token avalanche.


What This Means in Practice

Picture an agent wired up to Supabase + GitHub + Filesystem + Puppeteer. A realistic production setup.

Before dietmcp: ~30,000 tokens of tool schemas sitting in context every turn. The agent has less room to think, makes more mistakes, costs more per call.

After dietmcp: ~1,800 tokens of skill summaries. The agent knows what's available, knows the bash syntax to call it, and has 28,000 extra tokens for actual reasoning.

That's the difference between an agent that struggles with 20 tools and one that handles 78 without breaking a sweat.


Try It

    pip install dietmcp
    dietmcp config init
    dietmcp skills --all

Three commands. Your agent now has access to every MCP tool as a bash command.


The Broader Lesson

The best way to give an AI agent more capabilities is NOT to shove everything into its prompt.

It's to build a layer between the agent and its tools. Let the agent know what's available. Let the CLI handle how.

The agent doesn't need to understand JSON Schema. It doesn't need to see every parameter type and validation rule. It needs to know that read_file takes a path and returns contents. One line. Done.

This is the pattern: thin context, fat CLI. The agent stays focused. The tools stay accessible. The context window stays clean.

dietmcp is open source. 79 tools. 82% token reduction. 23,000x cache speedup.

If you're building with MCP and hitting context limits, this is the fix.
