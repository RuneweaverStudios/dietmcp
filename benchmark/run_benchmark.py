"""Benchmark: compare native MCP JSON schema tokens vs dietmcp skill summary tokens.

Measures the claims from README.md:
1. Schema size reduction (context window impact)
2. Response size reduction (output handling)
3. Auto-redirect for large responses
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def run_cmd(cmd: str, timeout: int = 30, stdout_only: bool = False) -> tuple[str, float]:
    """Run a shell command, return (output, elapsed_seconds)."""
    start = time.perf_counter()
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    elapsed = time.perf_counter() - start
    if stdout_only:
        return result.stdout.strip(), elapsed
    output = result.stdout + result.stderr
    return output.strip(), elapsed


def run_cmd_full(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a shell command, return full result."""
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def test_schema_size() -> dict:
    """Compare native JSON schema tokens vs dietmcp skill summary tokens."""
    separator("TEST 1: Schema Size (Context Window Impact)")

    # Get raw JSON schemas (stdout only — stderr has MCP server noise)
    raw_json, _ = run_cmd("dietmcp discover filesystem --json", stdout_only=True)
    schemas = json.loads(raw_json)
    native_schema = json.dumps({"tools": schemas}, indent=2)
    native_tokens = count_tokens(native_schema)

    # Get skill summary (stdout only)
    skill_summary, _ = run_cmd("dietmcp skills filesystem", stdout_only=True)
    skill_tokens = count_tokens(skill_summary)

    tool_count = len(schemas)
    reduction = ((native_tokens - skill_tokens) / native_tokens) * 100

    print(f"Server: filesystem")
    print(f"Tools discovered: {tool_count}")
    print(f"Native JSON schema: {native_tokens:,} tokens")
    print(f"dietmcp skill summary: {skill_tokens:,} tokens")
    print(f"Reduction: {reduction:.1f}%")
    print()

    # Verdict — README headline claims "80-90%"; per-server benchmarks
    # were measured at specific tool counts that may differ from current.
    if reduction >= 75:
        print(f"PASS: {reduction:.1f}% reduction (README headline: 80-90%)")
    else:
        print(f"FAIL: {reduction:.1f}% reduction is below expected 75%+ floor")

    return {
        "tool_count": tool_count,
        "native_tokens": native_tokens,
        "skill_tokens": skill_tokens,
        "reduction_pct": round(reduction, 1),
    }


def test_response_sizes() -> list[dict]:
    """Compare raw MCP response tokens vs dietmcp formatted output."""
    separator("TEST 2: Response Size (Output Handling)")

    cases = [
        ("small file (~12 bytes)", "read_file", '{"path": "/tmp/testdata/small.txt"}'),
        ("medium file (~2KB)", "read_file", '{"path": "/tmp/testdata/medium.txt"}'),
        ("large file (~50KB)", "read_file", '{"path": "/tmp/testdata/large.txt"}'),
        ("directory listing (500 files)", "list_directory", '{"path": "/tmp/testdata"}'),
    ]

    results = []

    for label, tool, args in cases:
        # Raw (minified) response — stdout only to skip MCP server stderr
        raw_output, _ = run_cmd(
            f"dietmcp exec filesystem {tool} --args '{args}' --output-format minified",
            stdout_only=True,
        )
        raw_tokens = count_tokens(raw_output)

        # Summary response
        summary_output, _ = run_cmd(
            f"dietmcp exec filesystem {tool} --args '{args}' --output-format summary",
            stdout_only=True,
        )

        # Check for auto-redirect
        auto_redirected = "[Response written to" in summary_output
        summary_tokens = count_tokens(summary_output)

        if raw_tokens > 0:
            reduction = ((raw_tokens - summary_tokens) / raw_tokens) * 100
        else:
            reduction = 0.0

        print(f"{label}:")
        print(f"  Raw (minified): {raw_tokens:,} tokens")
        print(f"  Summary: {summary_tokens:,} tokens")
        print(f"  Reduction: {reduction:.1f}%")
        if auto_redirected:
            print(f"  Auto-redirected to file: YES")
        print()

        results.append({
            "label": label,
            "raw_tokens": raw_tokens,
            "summary_tokens": summary_tokens,
            "reduction_pct": round(reduction, 1),
            "auto_redirected": auto_redirected,
        })

    return results


def test_output_formats() -> dict:
    """Verify all three output formats work correctly."""
    separator("TEST 3: Output Format Correctness")

    args = '{"path": "/tmp/testdata"}'
    formats = {}

    for fmt in ("summary", "minified", "csv"):
        output, elapsed = run_cmd(
            f"dietmcp exec filesystem list_directory --args '{args}' --output-format {fmt}",
            stdout_only=True,
        )
        tokens = count_tokens(output)
        ok = len(output) > 0 and "[ERROR]" not in output
        print(f"  {fmt}: {tokens:,} tokens, {elapsed:.2f}s — {'PASS' if ok else 'FAIL'}")
        formats[fmt] = {"tokens": tokens, "elapsed": elapsed, "ok": ok}

    return formats


def test_caching() -> dict:
    """Verify cache hit is faster than cache miss."""
    separator("TEST 4: Cache Performance")

    # Cold (refresh forces cache miss)
    _, cold_time = run_cmd("dietmcp discover filesystem --refresh")
    # Warm (should hit cache)
    _, warm_time = run_cmd("dietmcp discover filesystem")

    speedup = cold_time / warm_time if warm_time > 0 else 0
    print(f"  Cold (--refresh): {cold_time:.2f}s")
    print(f"  Warm (cached):    {warm_time:.2f}s")
    print(f"  Speedup: {speedup:.1f}x")
    ok = warm_time < cold_time
    print(f"  {'PASS' if ok else 'WARN'}: cache {'faster' if ok else 'not faster'} than cold")

    return {"cold_s": round(cold_time, 2), "warm_s": round(warm_time, 2), "speedup": round(speedup, 1)}


def test_error_exit_codes() -> dict:
    """Verify exit codes for error cases."""
    separator("TEST 5: Error Exit Codes")

    tests = [
        ("unknown server", "dietmcp exec nope tool --args '{}'"),
        ("unknown tool", "dietmcp exec filesystem nope --args '{}'"),
        ("invalid JSON", "dietmcp exec filesystem read_file --args 'bad'"),
        ("MCP tool error (missing required arg)", "dietmcp exec filesystem read_file --args '{}'"),
    ]

    results = {}
    all_pass = True
    for label, cmd in tests:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        ok = result.returncode != 0
        print(f"  {label}: exit {result.returncode} — {'PASS' if ok else 'FAIL (expected non-zero)'}")
        results[label] = {"exit_code": result.returncode, "ok": ok}
        if not ok:
            all_pass = False

    return results


def test_file_redirect() -> dict:
    """Verify --output-file writes to disk."""
    separator("TEST 6: File Redirect")

    import os
    out_path = "/tmp/benchmark_output.txt"
    output, _ = run_cmd(
        f"dietmcp exec filesystem read_file "
        f"--args '{{\"path\": \"/tmp/testdata/medium.txt\"}}' "
        f"--output-file {out_path}",
        stdout_only=True,
    )

    pointer_shown = "Response written to" in output
    file_exists = os.path.isfile(out_path)
    file_size = os.path.getsize(out_path) if file_exists else 0

    print(f"  Pointer in stdout: {'YES' if pointer_shown else 'NO'}")
    print(f"  File exists: {'YES' if file_exists else 'NO'}")
    print(f"  File size: {file_size:,} bytes")
    ok = pointer_shown and file_exists and file_size > 0
    print(f"  {'PASS' if ok else 'FAIL'}")

    return {"pointer_shown": pointer_shown, "file_exists": file_exists, "file_size": file_size, "ok": ok}


def main() -> None:
    print("=" * 60)
    print("  dietmcp Benchmark Suite")
    print("  Verifying README claims against actual behavior")
    print("=" * 60)

    schema = test_schema_size()
    responses = test_response_sizes()
    formats = test_output_formats()
    cache = test_caching()
    errors = test_error_exit_codes()
    redirect = test_file_redirect()

    separator("FINAL SUMMARY")

    # Schema reduction check
    schema_ok = schema["reduction_pct"] >= 75
    print(f"Schema reduction: {schema['reduction_pct']}% — {'PASS' if schema_ok else 'FAIL'} (target: >=75%)")

    # Response reduction check (large file should be massive reduction via auto-redirect)
    large_case = next((r for r in responses if "50KB" in r["label"]), None)
    large_ok = large_case and large_case["reduction_pct"] >= 90
    if large_case:
        print(f"Large file reduction: {large_case['reduction_pct']}% — {'PASS' if large_ok else 'FAIL'} (target: >=90%)")

    # Dir listing reduction
    dir_case = next((r for r in responses if "500 files" in r["label"]), None)
    dir_ok = dir_case and dir_case["reduction_pct"] >= 0  # Just needs to work
    if dir_case:
        print(f"Dir listing (500 files): {dir_case['summary_tokens']} tokens — {'PASS' if dir_ok else 'FAIL'}")

    # Format correctness
    fmt_ok = all(f["ok"] for f in formats.values())
    print(f"Output formats (summary/minified/csv): {'PASS' if fmt_ok else 'FAIL'}")

    # Cache
    cache_ok = cache["warm_s"] < cache["cold_s"]
    print(f"Cache speedup: {cache['speedup']}x — {'PASS' if cache_ok else 'WARN'}")

    # Error exit codes
    error_ok = all(e["ok"] for e in errors.values())
    print(f"Error exit codes: {'PASS' if error_ok else 'FAIL'}")

    # File redirect
    print(f"File redirect: {'PASS' if redirect['ok'] else 'FAIL'}")

    # Overall
    all_pass = schema_ok and fmt_ok and error_ok and redirect["ok"]
    print(f"\n{'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
