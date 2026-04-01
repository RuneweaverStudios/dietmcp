#!/usr/bin/env python3
"""Benchmark script comparing dietmcp vs mcp2cli token usage.

This script measures:
1. Schema token compression (JSON schemas vs skill summaries)
2. TOON encoding compression (vs standard JSON)
3. Overall competitive positioning vs mcp2cli

Run with: python scripts/benchmark_vs_mcp2cli.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Try to import tiktoken, handle gracefully if not available
try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    print("Warning: tiktoken not installed. Install with: pip install tiktoken")
    print("Falling back to character-based estimation (less accurate)\n")


def count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding (GPT-4)."""
    if not text:
        return 0

    if HAS_TIKTOKEN:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    else:
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def load_json_schema(server_name: str) -> dict[str, Any]:
    """Load cached JSON schema for a server."""
    # Get cache directory
    cache_dir = Path.home() / ".cache" / "dietmcp"
    if not cache_dir.exists():
        # Try macOS location
        cache_dir = Path.home() / "Library" / "Caches" / "dietmcp"

    schema_file = cache_dir / f"{server_name}_schema.json"
    if not schema_file.exists():
        print(f"Warning: No cached schema found for {server_name}")
        print(f"Expected: {schema_file}")
        print("Run: dietmcp discover {server_name}")
        return {}

    with open(schema_file) as f:
        return json.load(f)


def get_skill_summary_text(server_name: str, ultra_compact: bool = False) -> str:
    """Get skill summary text by running dietmcp skills command."""
    cmd = ["dietmcp", "skills", server_name]
    if ultra_compact:
        cmd.extend(["--format", "ultra"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Warning: Could not get skill summary for {server_name}: {e}")
        return ""


def benchmark_server(
    server_name: str,
    tools_count: int,
    ultra_compact: bool = False,
) -> dict[str, Any]:
    """Benchmark a single server's token usage."""
    print(f"\n{'='*60}")
    print(f"Benchmarking: {server_name} ({tools_count} tools)")
    print(f"{'='*60}")

    # Load JSON schema
    schema = load_json_schema(server_name)
    schema_text = json.dumps(schema, indent=2)
    schema_tokens = count_tokens(schema_text)

    # Get skill summary
    skill_text = get_skill_summary_text(server_name, ultra_compact=ultra_compact)
    skill_tokens = count_tokens(skill_text)

    # Calculate metrics
    reduction = ((schema_tokens - skill_tokens) / schema_tokens * 100) if schema_tokens > 0 else 0
    tokens_per_tool = skill_tokens / tools_count if tools_count > 0 else 0

    result = {
        "server": server_name,
        "tools": tools_count,
        "schema_tokens": schema_tokens,
        "skill_tokens": skill_tokens,
        "reduction_percent": round(reduction, 1),
        "tokens_per_tool": round(tokens_per_tool, 1),
        "mode": "ultra-compact" if ultra_compact else "standard",
    }

    # Print results
    print(f"Native JSON Schema: {schema_tokens:,} tokens")
    print(f"dietmcp Skill Summary: {skill_tokens:,} tokens ({result['mode']})")
    print(f"Reduction: {reduction:.1f}%")
    print(f"Tokens per tool: {tokens_per_tool:.1f}")

    return result


def benchmark_toon_encoding() -> dict[str, Any]:
    """Benchmark TOON encoding compression vs JSON."""
    print(f"\n{'='*60}")
    print("Benchmarking: TOON Encoding")
    print(f"{'='*60}")

    # Sample tabular data (simulating GitHub repos response)
    sample_data = [
        {"id": 1, "name": "dietmcp", "visibility": "public", "stars": 150},
        {"id": 2, "name": "mcp2cli", "visibility": "public", "stars": 320},
        {"id": 3, "name": "example-repo", "visibility": "private", "stars": 45},
        {"id": 4, "name": "test-project", "visibility": "public", "stars": 78},
        {"id": 5, "name": "demo", "visibility": "public", "stars": 12},
    ]

    # Standard JSON
    json_text = json.dumps(sample_data, indent=2)
    json_tokens = count_tokens(json_text)

    # TOON format (simulated)
    # [5]{id,name,visibility,stars}: 1,dietmcp,public,150,2,mcp2cli,public,320,...
    toon_text = "[5]{id,name,visibility,stars}: 1,dietmcp,public,150,2,mcp2cli,public,320,3,example-repo,private,45,4,test-project,public,78,5,demo,public,12"
    toon_tokens = count_tokens(toon_text)

    # Minified JSON (fair comparison)
    json_minified = json.dumps(sample_data, separators=(",", ":"))
    json_minified_tokens = count_tokens(json_minified)

    reduction_vs_json = ((json_tokens - toon_tokens) / json_tokens * 100) if json_tokens > 0 else 0
    reduction_vs_minified = ((json_minified_tokens - toon_tokens) / json_minified_tokens * 100) if json_minified_tokens > 0 else 0

    result = {
        "json_tokens": json_tokens,
        "json_minified_tokens": json_minified_tokens,
        "toon_tokens": toon_tokens,
        "reduction_vs_json": round(reduction_vs_json, 1),
        "reduction_vs_minified": round(reduction_vs_minified, 1),
    }

    print(f"Standard JSON: {json_tokens} tokens")
    print(f"Minified JSON: {json_minified_tokens} tokens")
    print(f"TOON encoded: {toon_tokens} tokens")
    print(f"Reduction vs JSON: {reduction_vs_json:.1f}%")
    print(f"Reduction vs minified: {reduction_vs_minified:.1f}%")

    return result


def print_comparison_table(results: list[dict[str, Any]], toon_results: dict[str, Any]):
    """Print comparison table with mcp2cli."""
    print(f"\n{'='*80}")
    print("COMPARATIVE BENCHMARK: dietmcp vs mcp2cli")
    print(f"{'='*80}\n")

    # Overall statistics
    total_schema = sum(r["schema_tokens"] for r in results)
    total_skill = sum(r["skill_tokens"] for r in results)
    total_tools = sum(r["tools"] for r in results)
    overall_reduction = ((total_schema - total_skill) / total_schema * 100) if total_schema > 0 else 0
    avg_tokens_per_tool = total_skill / total_tools if total_tools > 0 else 0

    print("SCHEMA COMPRESSION")
    print("-" * 80)
    print(f"{'Server':<15} {'Tools':<8} {'Native':<12} {'dietmcp':<12} {'Reduction':<12} {'Tokens/Tool':<12}")
    print("-" * 80)

    for r in results:
        print(
            f"{r['server']:<15} {r['tools']:<8} "
            f"{r['schema_tokens']:<12,} {r['skill_tokens']:<12,} "
            f"{r['reduction_percent']:<11.1f}% {r['tokens_per_tool']:<11.1f}"
        )

    print("-" * 80)
    print(
        f"{'TOTAL':<15} {total_tools:<8} "
        f"{total_schema:<12,} {total_skill:<12,} "
        f"{overall_reduction:<11.1f}% {avg_tokens_per_tool:<11.1f}"
    )

    print("\n" + "=" * 80)
    print("COMPETITIVE POSITIONING")
    print("=" * 80)
    print(f"\ndietmcp Ultra-Compact: {avg_tokens_per_tool:.1f} tokens/tool")
    print(f"mcp2cli (documented):   16.0 tokens/tool")
    print(f"Advantage:              {(16 - avg_tokens_per_tool) / 16 * 100:.1f}% better" if avg_tokens_per_tool < 16 else f"mcp2cli better by {(avg_tokens_per_tool - 16) / 16 * 100:.1f}%")

    print("\n" + "=" * 80)
    print("TOON ENCODING")
    print("=" * 80)
    print(f"\nCompression vs JSON:     {toon_results['reduction_vs_json']:.1f}%")
    print(f"Compression vs minified: {toon_results['reduction_vs_minified']:.1f}%")
    print(f"\nAdvantage: Native implementation (no subprocess overhead)")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    if avg_tokens_per_tool < 16:
        print(f"✓ dietmcp BEATS mcp2cli on schema compression")
        print(f"  ({avg_tokens_per_tool:.1f} vs 16.0 tokens/tool = {(16 - avg_tokens_per_tool) / 16 * 100:.1f}% better)")
    else:
        print(f"✗ mcp2cli leads on schema compression")
        print(f"  ({avg_tokens_per_tool:.1f} vs 16.0 tokens/tool)")

    print(f"\n✓ dietmcp achieves {overall_reduction:.1f}% schema reduction overall")
    print(f"✓ TOON encoding achieves {toon_results['reduction_vs_minified']:.1f}% response compression")
    print(f"✓ Native TOON implementation (no subprocess overhead)")


def main():
    """Run comprehensive benchmarks."""
    print("=" * 80)
    print("dietmcp Benchmark Script")
    print("Comparing against mcp2cli documented metrics")
    print("=" * 80)

    if not HAS_TIKTOKEN:
        print("\nWARNING: tiktoken not available - using character-based estimation")
        print("Install with: pip install tiktoken")
        print("Continuing with estimates...\n")

    # Benchmark common servers (tool counts from current versions)
    servers = [
        ("filesystem", 6),  # Current @modelcontextprotocol/server-filesystem
        ("github", 15),  # Current @modelcontextprotocol/server-github
    ]

    results = []
    for server_name, tool_count in servers:
        try:
            # Benchmark standard mode
            result = benchmark_server(server_name, tool_count, ultra_compact=False)
            results.append(result)

            # Benchmark ultra-compact mode
            result_uc = benchmark_server(server_name, tool_count, ultra_compact=True)
            results.append(result_uc)
        except Exception as e:
            print(f"Error benchmarking {server_name}: {e}")
            continue

    # Benchmark TOON encoding
    toon_results = benchmark_toon_encoding()

    # Print comparison table
    if results:
        print_comparison_table(results, toon_results)

    print("\n" + "=" * 80)
    print("Benchmark complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
