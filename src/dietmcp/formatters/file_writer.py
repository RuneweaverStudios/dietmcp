"""File output redirect for large responses."""

from __future__ import annotations

import tempfile
from pathlib import Path

from dietmcp.models.response import TunedResponse

# Security: Define allowed base directories for file writes
# Prevents path traversal attacks by restricting write locations
_ALLOWED_BASE_DIRS = [
    Path(tempfile.gettempdir()),  # Temp directory
    Path.cwd(),  # Current working directory
]


def write_response(
    response: TunedResponse,
    output_path: str | None,
    max_stdout_size: int,
) -> TunedResponse:
    """Optionally redirect response content to a file.

    Rules:
    1. If output_path is specified, always write to that file.
    2. If content exceeds max_stdout_size, write to a temp file.
    3. Otherwise, return the response unchanged.

    Returns a new TunedResponse with output_path set if written to file.
    """
    content = response.content

    if output_path:
        _write_file(output_path, content)
        return TunedResponse(
            format_name=response.format_name,
            content=content,
            is_error=response.is_error,
            was_truncated=response.was_truncated,
            output_path=output_path,
        )

    if len(content) > max_stdout_size:
        tmp_path = _write_temp(content)
        return TunedResponse(
            format_name=response.format_name,
            content=content,
            is_error=response.is_error,
            was_truncated=response.was_truncated,
            output_path=tmp_path,
        )

    return response


def _write_file(path: str, content: str) -> None:
    target = Path(path).resolve()

    # Security: Validate path is within allowed directories
    # Prevents path traversal attacks (e.g., ../../../etc/passwd)
    if not any(
        str(target).startswith(str(d.resolve()))
        for d in _ALLOWED_BASE_DIRS
    ):
        raise ValueError(
            f"Path traversal denied: {path} is outside allowed directories"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _write_temp(content: str) -> str:
    fd, path = tempfile.mkstemp(prefix="dietmcp_", suffix=".txt")
    with open(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path
