#!/usr/bin/env python3
"""Benchmark: compare token usage between native MCP JSON schemas and dietmcp skill summaries.

This script measures the token reduction achieved by dietmcp's skill summary format
versus raw JSON tool schemas. It uses tiktoken for accurate token counting.

Usage:
    python benchmarks/token_comparison.py

The benchmark uses representative tool schemas from real MCP servers:
- filesystem (6 tools)
- github (15 tools)
- puppeteer (12 tools)
- context7 (8 tools)
- supabase (37 tools)

DEV NOTE: Token counts use cl100k_base encoding (GPT-4/Claude-compatible).
Real-world results may vary slightly depending on the actual tool descriptions
from live MCP servers. These benchmarks use realistic approximations.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dietmcp.models.tool import ToolDefinition
from dietmcp.core.skills_generator import _categorize_tools, _truncate
from dietmcp.models.skill import SkillCategory, SkillEntry, SkillSummary


# ---------------------------------------------------------------------------
# Representative tool schemas from real MCP servers
# ---------------------------------------------------------------------------

_FILESYSTEM_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this to examine existing files you need to understand or modify.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file to read"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Creates parent directories as needed. Only use when you are confident in the full file content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path where the file should be written"},
                "content": {"type": "string", "description": "Complete content to write to the file"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "Get a detailed listing of all files and directories in a specified path. Results include file names and indicate whether each entry is a file or directory. Use this to understand the structure of a directory before performing operations on specific files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the directory to list"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Recursively search for files and directories matching a pattern. Searches through all subdirectories from the starting path. The pattern can match against file names and directory names.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Starting directory for the search"},
                "pattern": {"type": "string", "description": "Search pattern to match against file names"},
                "regex": {"type": "boolean", "description": "Whether the pattern is a regular expression"},
            },
            "required": ["path", "pattern"],
        },
    },
    {
        "name": "get_file_info",
        "description": "Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, modification time, access time, type (file/directory), and permissions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file or directory"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "move_file",
        "description": "Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail. Parent directories of the destination are created as needed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Current absolute path of the file or directory"},
                "destination": {"type": "string", "description": "New absolute path for the file or directory"},
            },
            "required": ["source", "destination"],
        },
    },
]


def _generate_github_tools() -> list[dict]:
    """Generate representative GitHub MCP tool schemas."""
    tools = []
    github_ops = [
        ("create_issue", "Create a new issue in a GitHub repository", {"owner": "str", "repo": "str", "title": "str", "body": "str", "labels": "array", "assignees": "array"}),
        ("list_issues", "List issues in a repository with optional filtering", {"owner": "str", "repo": "str", "state": "str", "labels": "str", "sort": "str", "direction": "str", "per_page": "int"}),
        ("get_issue", "Get details of a specific issue", {"owner": "str", "repo": "str", "issue_number": "int"}),
        ("update_issue", "Update an existing issue", {"owner": "str", "repo": "str", "issue_number": "int", "title": "str", "body": "str", "state": "str"}),
        ("create_pull_request", "Create a new pull request", {"owner": "str", "repo": "str", "title": "str", "body": "str", "head": "str", "base": "str", "draft": "bool"}),
        ("list_pull_requests", "List pull requests in a repository", {"owner": "str", "repo": "str", "state": "str", "head": "str", "base": "str", "sort": "str"}),
        ("merge_pull_request", "Merge a pull request", {"owner": "str", "repo": "str", "pull_number": "int", "commit_title": "str", "merge_method": "str"}),
        ("search_repositories", "Search for repositories on GitHub", {"query": "str", "sort": "str", "order": "str", "per_page": "int"}),
        ("search_code", "Search for code across GitHub repositories", {"query": "str", "sort": "str", "order": "str", "per_page": "int"}),
        ("get_file_contents", "Get the contents of a file from a repository", {"owner": "str", "repo": "str", "path": "str", "ref": "str"}),
        ("create_branch", "Create a new branch in a repository", {"owner": "str", "repo": "str", "branch": "str", "from_branch": "str"}),
        ("list_commits", "List commits in a repository", {"owner": "str", "repo": "str", "sha": "str", "per_page": "int"}),
        ("create_comment", "Create a comment on an issue or PR", {"owner": "str", "repo": "str", "issue_number": "int", "body": "str"}),
        ("list_branches", "List branches in a repository", {"owner": "str", "repo": "str", "per_page": "int"}),
        ("get_repository", "Get details of a repository", {"owner": "str", "repo": "str"}),
    ]
    for name, desc, params in github_ops:
        props = {}
        for pname, ptype in params.items():
            type_map = {"str": "string", "int": "integer", "bool": "boolean", "array": "array"}
            props[pname] = {"type": type_map.get(ptype, ptype), "description": f"The {pname.replace('_', ' ')} parameter"}
        tools.append({
            "name": name,
            "description": desc,
            "inputSchema": {
                "type": "object",
                "properties": props,
                "required": list(params.keys())[:2],
            },
        })
    return tools


def _generate_puppeteer_tools() -> list[dict]:
    """Generate representative Puppeteer MCP tool schemas."""
    tools = []
    puppeteer_ops = [
        ("navigate", "Navigate the browser to a URL", {"url": "str"}),
        ("screenshot", "Take a screenshot of the current page", {"name": "str", "selector": "str", "width": "int", "height": "int"}),
        ("click", "Click an element on the page", {"selector": "str"}),
        ("fill", "Fill an input field with text", {"selector": "str", "value": "str"}),
        ("select", "Select an option from a dropdown", {"selector": "str", "value": "str"}),
        ("hover", "Hover over an element", {"selector": "str"}),
        ("evaluate", "Execute JavaScript in the browser context", {"script": "str"}),
        ("get_content", "Get the text content of the page or an element", {"selector": "str"}),
        ("wait_for_selector", "Wait for an element to appear", {"selector": "str", "timeout": "int"}),
        ("go_back", "Navigate back in browser history", {}),
        ("go_forward", "Navigate forward in browser history", {}),
        ("get_page_url", "Get the current page URL", {}),
    ]
    for name, desc, params in puppeteer_ops:
        props = {p: {"type": "string" if t == "str" else "integer", "description": f"The {p}"} for p, t in params.items()}
        tools.append({
            "name": name,
            "description": desc,
            "inputSchema": {"type": "object", "properties": props, "required": list(params.keys())[:1]},
        })
    return tools


def _generate_context7_tools() -> list[dict]:
    """Generate representative Context7 MCP tool schemas."""
    tools = []
    c7_ops = [
        ("resolve_library", "Resolve a library name to its Context7 ID", {"libraryName": "str"}),
        ("get_library_docs", "Get documentation for a library", {"context7CompatibleLibraryID": "str", "topic": "str", "tokens": "int"}),
        ("search_libraries", "Search for libraries", {"query": "str", "limit": "int"}),
        ("get_library_versions", "Get available versions for a library", {"libraryID": "str"}),
        ("get_code_examples", "Get code examples for a library", {"libraryID": "str", "topic": "str", "limit": "int"}),
        ("get_changelog", "Get changelog for a library version", {"libraryID": "str", "version": "str"}),
        ("compare_versions", "Compare two versions of a library", {"libraryID": "str", "fromVersion": "str", "toVersion": "str"}),
        ("get_api_reference", "Get API reference for a specific module", {"libraryID": "str", "module": "str"}),
    ]
    for name, desc, params in c7_ops:
        props = {p: {"type": "string" if t == "str" else "integer", "description": f"{p.replace('_', ' ')}"} for p, t in params.items()}
        tools.append({
            "name": name,
            "description": desc,
            "inputSchema": {"type": "object", "properties": props, "required": list(params.keys())[:1]},
        })
    return tools


def _generate_supabase_tools() -> list[dict]:
    """Generate representative Supabase MCP tool schemas."""
    tools = []
    sb_ops = [
        ("list_tables", "List all tables in the database", {"schema": "str"}),
        ("get_table_schema", "Get the schema of a table", {"table_name": "str", "schema": "str"}),
        ("execute_sql", "Execute a SQL query", {"query": "str", "params": "array"}),
        ("insert_rows", "Insert rows into a table", {"table": "str", "rows": "array", "returning": "str"}),
        ("update_rows", "Update rows in a table", {"table": "str", "set": "object", "match": "object"}),
        ("delete_rows", "Delete rows from a table", {"table": "str", "match": "object"}),
        ("select_rows", "Select rows from a table", {"table": "str", "columns": "str", "filter": "object", "limit": "int", "order": "str"}),
        ("create_table", "Create a new table", {"table_name": "str", "columns": "array", "schema": "str"}),
        ("alter_table", "Alter a table structure", {"table_name": "str", "operations": "array"}),
        ("drop_table", "Drop a table", {"table_name": "str", "cascade": "bool"}),
        ("list_functions", "List database functions", {"schema": "str"}),
        ("create_function", "Create a database function", {"name": "str", "definition": "str", "args": "array", "returns": "str", "language": "str"}),
        ("list_policies", "List RLS policies", {"table_name": "str"}),
        ("create_policy", "Create a RLS policy", {"table_name": "str", "name": "str", "definition": "str", "command": "str", "check": "str"}),
        ("list_triggers", "List triggers on a table", {"table_name": "str"}),
        ("create_trigger", "Create a trigger", {"table_name": "str", "name": "str", "function_name": "str", "events": "array", "timing": "str"}),
        ("list_indexes", "List indexes on a table", {"table_name": "str"}),
        ("create_index", "Create an index", {"table_name": "str", "columns": "array", "unique": "bool", "name": "str"}),
        ("get_migrations", "List applied migrations", {"schema": "str"}),
        ("create_migration", "Create a new migration", {"name": "str", "sql": "str"}),
        ("apply_migration", "Apply a pending migration", {"migration_id": "str"}),
        ("rollback_migration", "Rollback a migration", {"migration_id": "str"}),
        ("list_storage_buckets", "List storage buckets", {}),
        ("create_storage_bucket", "Create a storage bucket", {"name": "str", "public": "bool", "file_size_limit": "int"}),
        ("upload_file", "Upload a file to storage", {"bucket": "str", "path": "str", "content": "str", "content_type": "str"}),
        ("list_files", "List files in a storage bucket", {"bucket": "str", "path": "str", "limit": "int"}),
        ("delete_file", "Delete a file from storage", {"bucket": "str", "path": "str"}),
        ("get_project_settings", "Get project settings", {}),
        ("list_api_keys", "List API keys", {}),
        ("get_auth_config", "Get auth configuration", {}),
        ("update_auth_config", "Update auth configuration", {"config": "object"}),
        ("list_users", "List auth users", {"page": "int", "per_page": "int"}),
        ("create_user", "Create a new auth user", {"email": "str", "password": "str", "user_metadata": "object"}),
        ("delete_user", "Delete an auth user", {"user_id": "str"}),
        ("list_edge_functions", "List edge functions", {}),
        ("deploy_edge_function", "Deploy an edge function", {"name": "str", "code": "str"}),
        ("get_logs", "Get project logs", {"type": "str", "limit": "int", "start": "str", "end": "str"}),
        ("get_database_stats", "Get database statistics", {}),
    ]
    for name, desc, params in sb_ops:
        type_map = {"str": "string", "int": "integer", "bool": "boolean", "array": "array", "object": "object"}
        props = {p: {"type": type_map.get(t, t), "description": f"The {p.replace('_', ' ')}"} for p, t in params.items()}
        tools.append({
            "name": name,
            "description": desc,
            "inputSchema": {"type": "object", "properties": props, "required": list(params.keys())[:1] if params else []},
        })
    return tools


# ---------------------------------------------------------------------------
# Assemble server data (must come after helper function definitions)
# ---------------------------------------------------------------------------

MOCK_SERVERS: dict[str, list[dict]] = {
    "filesystem": _FILESYSTEM_TOOLS,
    "github": _generate_github_tools(),
    "puppeteer": _generate_puppeteer_tools(),
    "context7": _generate_context7_tools(),
    "supabase": _generate_supabase_tools(),
}


# ---------------------------------------------------------------------------
# Token counting (uses a simple word-based approximation if tiktoken unavailable)
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken if available, else approximate."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Approximate: ~4 chars per token for English/JSON
        return len(text) // 4


# ---------------------------------------------------------------------------
# Skill summary generation (inline, no MCP connection needed)
# ---------------------------------------------------------------------------

def generate_skill_text(server_name: str, raw_tools: list[dict]) -> str:
    """Generate a skill summary string from raw tool dicts."""
    tools = [
        ToolDefinition(
            name=t["name"],
            description=t["description"],
            input_schema=t["inputSchema"],
            server_name=server_name,
        )
        for t in raw_tools
    ]

    grouped = _categorize_tools(tools)
    categories = tuple(
        SkillCategory(
            name=cat_name,
            tools=tuple(
                SkillEntry(
                    signature=tool.compact_signature(),
                    description=_truncate(tool.description, 60),
                )
                for tool in cat_tools
            ),
        )
        for cat_name, cat_tools in sorted(grouped.items())
    )

    summary = SkillSummary(
        server_name=server_name,
        tool_count=len(tools),
        categories=categories,
        exec_syntax=f"dietmcp exec {server_name} <tool> --args '{{\"key\": \"value\"}}'",
    )
    return summary.render()


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def run_benchmark() -> None:
    print("=" * 70)
    print("dietmcp Token Usage Benchmark")
    print("=" * 70)
    print()

    total_native = 0
    total_skill = 0
    results = []

    for server_name, raw_tools in MOCK_SERVERS.items():
        # Native JSON schema (what gets loaded into context window normally)
        native_json = json.dumps(
            {"tools": raw_tools},
            indent=2,
        )
        native_tokens = count_tokens(native_json)

        # dietmcp skill summary
        skill_text = generate_skill_text(server_name, raw_tools)
        skill_tokens = count_tokens(skill_text)

        reduction = ((native_tokens - skill_tokens) / native_tokens) * 100

        results.append({
            "server": server_name,
            "tools": len(raw_tools),
            "native_tokens": native_tokens,
            "skill_tokens": skill_tokens,
            "reduction": reduction,
        })

        total_native += native_tokens
        total_skill += skill_tokens

    # Print results table
    print(f"{'Server':<15} {'Tools':>5} {'Native JSON':>12} {'Skill Summary':>14} {'Reduction':>10}")
    print("-" * 60)
    for r in results:
        print(
            f"{r['server']:<15} {r['tools']:>5} "
            f"{r['native_tokens']:>10,} tk "
            f"{r['skill_tokens']:>10,} tk "
            f"{r['reduction']:>8.1f}%"
        )
    print("-" * 60)
    total_reduction = ((total_native - total_skill) / total_native) * 100
    tool_count = sum(r["tools"] for r in results)
    print(
        f"{'TOTAL':<15} {tool_count:>5} "
        f"{total_native:>10,} tk "
        f"{total_skill:>10,} tk "
        f"{total_reduction:>8.1f}%"
    )

    print()
    print("=" * 70)
    print("Response Size Benchmark")
    print("=" * 70)
    print()

    # Simulate response sizes
    response_scenarios = [
        ("File read (2KB)", "x" * 2048, "summary"),
        ("File read (50KB)", "x" * 51200, "summary"),
        ("DB schema (20 tables)", json.dumps([{"table": f"table_{i}", "columns": [{"name": f"col_{j}", "type": "text"} for j in range(8)]} for i in range(20)], indent=2), "summary"),
        ("Search results (100)", json.dumps([{"file": f"src/module_{i}.py", "line": i * 10, "match": f"function_{i}()"} for i in range(100)], indent=2), "csv"),
        ("Dir listing (500)", json.dumps([{"name": f"file_{i:04d}.txt", "size": 1024 + i, "modified": "2026-03-14"} for i in range(500)], indent=2), "csv"),
    ]

    print(f"{'Scenario':<25} {'Raw Response':>12} {'dietmcp Output':>15} {'Reduction':>10}")
    print("-" * 65)

    from dietmcp.formatters.summary_formatter import SummaryFormatter
    from dietmcp.formatters.csv_formatter import CsvFormatter
    from dietmcp.models.tool import ToolResult

    for scenario, raw_content, fmt_name in response_scenarios:
        raw_tokens = count_tokens(raw_content)

        tool_result = ToolResult(content=[{"type": "text", "text": raw_content}])
        if fmt_name == "csv":
            formatter = CsvFormatter()
        else:
            formatter = SummaryFormatter()

        # Use a reasonable max_size (what an agent would see)
        formatted = formatter.format(tool_result, max_size=2000)

        # If auto-redirect would kick in (>50KB), agent sees only a pointer
        if len(raw_content) > 50000:
            output_text = f"[Response written to /tmp/dietmcp_xyz.txt ({len(raw_content):,} chars)]"
        else:
            output_text = formatted.content

        output_tokens = count_tokens(output_text)
        reduction = ((raw_tokens - output_tokens) / raw_tokens) * 100 if raw_tokens > 0 else 0

        print(
            f"{scenario:<25} {raw_tokens:>10,} tk "
            f"{output_tokens:>11,} tk "
            f"{reduction:>8.1f}%"
        )

    print()
    print("=" * 70)
    print("Cache Performance")
    print("=" * 70)
    print()

    from dietmcp.cache.tool_cache import ToolCache
    from dietmcp.models.server import ServerConfig
    import tempfile

    cache_dir = Path(tempfile.mkdtemp())
    cache = ToolCache(cache_dir)
    config = ServerConfig(name="benchmark", command="echo", args=("test",))
    tools = [
        ToolDefinition(
            name=f"tool_{i}", description=f"Tool {i}", input_schema={}, server_name="benchmark"
        )
        for i in range(50)
    ]

    # Measure write
    start = time.perf_counter()
    for _ in range(100):
        cache.put("benchmark", config, tools)
    write_time = (time.perf_counter() - start) / 100

    # Measure read (cache hit)
    start = time.perf_counter()
    for _ in range(1000):
        cache.get("benchmark", config)
    read_time = (time.perf_counter() - start) / 1000

    print(f"Cache write (50 tools):  {write_time*1000:.2f} ms avg")
    print(f"Cache read  (50 tools):  {read_time*1000:.2f} ms avg")
    print(f"Speedup vs live discovery: ~{2000/max(read_time*1000, 0.01):.0f}x (assuming 2s live fetch)")

    # Cleanup
    import shutil
    shutil.rmtree(cache_dir, ignore_errors=True)

    print()
    print("Done.")


if __name__ == "__main__":
    run_benchmark()
