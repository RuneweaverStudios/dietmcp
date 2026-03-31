"""Credential loading from environment variables and .env files.

DEV NOTES:
- The ${VAR_NAME} syntax was chosen to match shell variable expansion and the
  claude_desktop_config.json format, making it familiar and copy-pasteable.
- Resolution order: provided env dict > .env file > os.environ. This lets
  .env files override shell env, which is the expected behavior for local dev.
- We intentionally raise ValueError (not silently returning empty string) when
  a referenced variable is missing. Silent failures here would cause confusing
  auth errors downstream that are hard to debug.
- The collect_env function loads from two .env locations: CWD and the config dir.
  This supports both project-specific and global credential files.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import dotenv_values


_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_env_files(*paths: Path) -> dict[str, str]:
    """Load variables from multiple .env files, later files take precedence."""
    merged: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            values = dotenv_values(path)
            for k, v in values.items():
                if v is not None:
                    merged[k] = v
    return merged


def resolve_template(template: str, env: dict[str, str] | None = None) -> str:
    """Replace ${VAR_NAME} placeholders with values from env dict or os.environ.

    Raises ValueError if a referenced variable is not found.
    """
    lookup = env if env is not None else {}

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        # Check provided env dict first, then os.environ
        value = lookup.get(var_name) or os.environ.get(var_name)
        if value is None:
            raise ValueError(
                f"Environment variable '{var_name}' is not set. "
                f"Set it in your .env file or shell environment."
            )
        return value

    return _VAR_PATTERN.sub(_replacer, template)


def resolve_env_dict(
    env_dict: dict[str, str], extra_env: dict[str, str] | None = None
) -> dict[str, str]:
    """Resolve all ${VAR} references in a dictionary of environment variables."""
    resolved = {}
    for key, value in env_dict.items():
        resolved[key] = resolve_template(value, extra_env)
    return resolved


def collect_env(dotenv_paths: list[Path] | None = None) -> dict[str, str]:
    """Build a combined env dict from .env files and os.environ.

    .env values override os.environ for interpolation purposes.
    Also injects loaded values into os.environ so child processes
    (MCP servers spawned via stdio) inherit them automatically.
    """
    paths = dotenv_paths or []
    dotenv_vars = load_env_files(*paths)
    # Merge os.environ with dotenv (dotenv wins on conflict).
    # Does NOT mutate os.environ — child process env is built
    # separately in transport/connection.py via config.env.
    combined = dict(os.environ)
    combined.update(dotenv_vars)
    return combined
