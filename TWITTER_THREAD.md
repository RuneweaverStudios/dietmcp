How I Got 78 MCP Tools Into One Agent Without Everything Falling Apart

So I've been deep in the MCP rabbit hole for a while now. Building agents, wiring up servers, the whole thing. And I kept running into this wall that honestly drove me a little crazy before I figured out what was happening.

Every time I added a new MCP server, my agent got worse. Not a little worse. Noticeably, measurably worse. More hallucinations. Slower responses. It started making up tool names that didn't exist. I'm sitting there thinking "I just gave you MORE capabilities, why are you dumber now?"

Turns out, the answer was staring me in the face the whole time.


The thing nobody warns you about

When you connect an MCP server to an agent, every single tool on that server gets its full JSON schema injected into the prompt. The name, the description, every parameter, every type annotation, every nested object. All of it. Every turn. Whether the agent uses the tool or not.

I did the math one afternoon and almost spit out my coffee. My filesystem server alone, six tools, was eating over 2,000 tokens of context. Just sitting there. Doing nothing. My GitHub server was closer to 3,000. Supabase? Over 4,000.

I had four servers connected. That's roughly 10,000 tokens of JSON schema clogging up the prompt on every single turn. Before my agent even started thinking about the actual task, a quarter of its working memory was already occupied by tool definitions it probably wasn't going to touch.

No wonder it was getting confused. The poor thing was trying to reason through a wall of JSON.


The moment it clicked

I was debugging a particularly bad hallucination. The agent kept calling a tool called "query_database" that didn't exist on any of my servers. And I noticed something. When I asked the same agent to do something with bash, it was flawless. curl commands, grep pipelines, file manipulation. Perfect every time.

And that's when it hit me. The agent already knows bash. It's really, really good at bash. So why am I cramming thousands of tokens of JSON schema into its context when I could just... give it a bash command to run?

What if every MCP tool was just a CLI call?

Instead of the agent needing to understand the full schema for read_file, the type definitions, the property descriptions, the required fields, it just needs to know:

    dietmcp exec filesystem read_file --args '{"path": "/tmp/file.txt"}'

One line. That's it. The agent already knows how to construct a command like that. I don't need to teach it anything.


Building the thing

I spent about a week putting together dietmcp. It's a Python CLI that sits between the agent and whatever MCP servers you have. The idea is pretty straightforward. Instead of loading all the tool schemas into the prompt, you give the agent a short cheat sheet and let it call tools through the command line.

The cheat sheet is what I call a "skill summary." It takes something like this (the actual JSON that normally sits in context):

    {
      "tools": [{
        "name": "read_file",
        "description": "Read the complete contents of a file from the file system.
         Handles various text encodings and provides detailed error messages
         if the file cannot be read.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to read"}
          },
          "required": ["path"]
        }
      }, ...]
    }

And turns it into this:

    filesystem (6 tools)

    File Operations
    - read_file(path: str) -- Read file contents
    - write_file(path: str, content: str) -- Write content to file
    - move_file(source: str, destination: str) -- Move or rename files

    Search
    - search_files(path: str, pattern: str, ?regex: bool) -- Search for files

    Exec: dietmcp exec filesystem <tool> --args '{"key": "value"}'

First version is 2,147 tokens. Second version is 189. Same information, just compressed into the format an agent actually needs. It doesn't need to know the JSON Schema type system. It needs to know what the tool does and what to pass it.


Did it actually work though

Yeah. Better than I expected, honestly.

I set up a benchmark with 5 MCP servers: filesystem, github, puppeteer, context7, and supabase. 79 tools total. Here's what the numbers looked like:

    Server          Tools    Native JSON    Skill Summary    Reduction
    ---------------------------------------------------------------
    filesystem          6    999 tokens     175 tokens       82.5%
    github             15    2,961 tokens   471 tokens       84.1%
    puppeteer          12    1,093 tokens   229 tokens       79.0%
    context7            8    962 tokens     215 tokens       77.7%
    supabase           38    4,250 tokens   723 tokens       83.0%
    ---------------------------------------------------------------
    TOTAL              79    10,265 tokens  1,813 tokens     82.3%

Over 8,000 tokens freed up. Every turn. That's a lot of room for the agent to actually think.

But the part that surprised me more was the output handling. I hadn't really thought about this going in, but it ended up being just as important.

When an agent reads a big file through native MCP, the entire contents get dumped into the conversation. A 50KB log file? That's 12,800 tokens just sitting in the chat history. Forever. For a file the agent probably only needed three lines from.

With dietmcp, anything over 50KB gets written to a temp file automatically. The agent sees:

    [Response written to /tmp/dietmcp_xyz.txt (51,200 chars)]

Fourteen tokens. And then the agent can grep through that file for what it actually needs. It went from "here's the entire haystack in your context window" to "the haystack is over there, go find the needle." Way better.


The cache thing

One problem I hadn't anticipated: MCP tool discovery is slow. Like, 2 seconds slow. Every time you connect to a server, it has to spawn the process, do the handshake, fetch the tool list. For a CLI that gets called every turn, that's painful.

So I added a file-based cache. Tool schemas get saved to disk after the first fetch, and subsequent calls just read the cache file. Cache reads take about 0.09 milliseconds. That's a 23,000x speedup over live discovery. Cache expires after an hour, or whenever you change the server config.

It uses atomic writes (write to a temp file, then rename) so you don't get corruption if two agent calls happen simultaneously. Probably overkill for most use cases, but I've been burned by cache corruption before and I'd rather not debug that again.


Keeping secrets secret

This one kept me up at night a little. When you're building a bridge between an AI agent and tools that can read your filesystem, push to your GitHub, and query your database, you really don't want credentials leaking anywhere.

The config file uses placeholder syntax, ${GITHUB_TOKEN} instead of the actual token. Credentials get resolved from .env files at runtime. They never show up in CLI arguments (so they're not visible in process lists), and all error output runs through a masking layer that replaces known secret values with asterisks.

Is it paranoid? Maybe. But the alternative is an agent accidentally printing your GitHub token in a traceback, and I've seen weirder things happen.


What I'd do differently

The tool categorization is pretty basic right now. It groups tools by keyword matching. Anything with "file" or "read" in the name goes under "File Operations," anything with "search" goes under "Search." It works okay for most servers but it's not amazing. I've been thinking about whether it's worth using embeddings for smarter grouping, but honestly the simple version handles 90% of cases fine.

The other thing is connection handling. Right now every invocation opens a fresh connection to the MCP server. It's simple and avoids stale connection bugs, but it means the first call to a server (before caching kicks in) is always that 2-second hit. A persistent connection daemon would be faster, but it's also a lot more complexity to manage. For now the cache makes this a non-issue after the first call.


The takeaway

The thing that keeps sticking with me is how simple the core idea is. Don't put everything in the prompt. The agent doesn't need to internalize the full documentation for every tool it might use. It needs a table of contents and a way to call things.

I keep thinking of it as "thin context, fat CLI." Give the agent just enough to know what's available and how to invoke it. Let the actual tool complexity live outside the context window, in a CLI it already knows how to use.

I had an agent running Supabase, GitHub, filesystem, and Puppeteer all at once. 78 tools. And it was handling them fine. Before dietmcp, it would start falling apart around 20. That's not a small difference.

If you want to try it:

    pip install dietmcp
    dietmcp config init
    dietmcp skills --all

Three commands. The config mirrors the claude_desktop_config.json format so you can copy your existing server definitions straight in.

It's open source. I'd love to hear what breaks.
