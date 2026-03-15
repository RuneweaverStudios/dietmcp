"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dietmcp.config.schema import DietMcpConfig
from dietmcp.models.server import ServerConfig
from dietmcp.models.tool import ToolDefinition, ToolResult


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_config_path() -> Path:
    return FIXTURES_DIR / "sample_config.json"


@pytest.fixture
def sample_config(sample_config_path: Path) -> DietMcpConfig:
    raw = json.loads(sample_config_path.read_text())
    return DietMcpConfig.model_validate(raw)


@pytest.fixture
def sample_tool_schemas() -> list[dict]:
    path = FIXTURES_DIR / "sample_tool_schemas.json"
    return json.loads(path.read_text())


@pytest.fixture
def sample_tools(sample_tool_schemas: list[dict]) -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name=t["name"],
            description=t["description"],
            input_schema=t["input_schema"],
            server_name="filesystem",
        )
        for t in sample_tool_schemas
    ]


@pytest.fixture
def sample_server_config() -> ServerConfig:
    return ServerConfig(
        name="filesystem",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-filesystem", "/tmp"),
    )


@pytest.fixture
def text_tool_result() -> ToolResult:
    return ToolResult(
        content=[{"type": "text", "text": "Hello, world! This is the content of the file."}],
        is_error=False,
    )


@pytest.fixture
def error_tool_result() -> ToolResult:
    return ToolResult(
        content=[{"type": "text", "text": "FileNotFoundError: /tmp/nonexistent.txt"}],
        is_error=True,
    )


@pytest.fixture
def tabular_tool_result() -> ToolResult:
    data = json.dumps([
        {"name": "README.md", "size": 2847, "modified": "2026-03-14"},
        {"name": "src/main.py", "size": 1203, "modified": "2026-03-15"},
        {"name": "tests/test_main.py", "size": 890, "modified": "2026-03-15"},
    ])
    return ToolResult(
        content=[{"type": "text", "text": data}],
        is_error=False,
    )


@pytest.fixture
def large_tool_result() -> ToolResult:
    # Generate a large text response (~100KB)
    large_text = "x" * 100_000
    return ToolResult(
        content=[{"type": "text", "text": large_text}],
        is_error=False,
    )
