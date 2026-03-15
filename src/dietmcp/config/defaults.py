"""Default paths and constants."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir, user_cache_dir


APP_NAME = "dietmcp"

CONFIG_DIR = Path(user_config_dir(APP_NAME))
CACHE_DIR = Path(user_cache_dir(APP_NAME))
CONFIG_FILE = CONFIG_DIR / "servers.json"

# Project root: the directory containing the installed dietmcp package.
# This is where we look for .env first.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

DEFAULT_CACHE_TTL = 3600
DEFAULT_OUTPUT_FORMAT = "summary"
DEFAULT_MAX_RESPONSE_SIZE = 50_000

# Ordered list of directories to search for .env files.
# Later entries take precedence over earlier ones.
ENV_SEARCH_PATHS: list[Path] = [
    CONFIG_DIR / ".env",       # Global: ~/Library/Application Support/dietmcp/.env
    PROJECT_ROOT / ".env",     # Project root: where dietmcp is installed
]
