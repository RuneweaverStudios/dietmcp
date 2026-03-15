"""Default paths and constants."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir, user_cache_dir


APP_NAME = "dietmcp"

CONFIG_DIR = Path(user_config_dir(APP_NAME))
CACHE_DIR = Path(user_cache_dir(APP_NAME))
CONFIG_FILE = CONFIG_DIR / "servers.json"

DEFAULT_CACHE_TTL = 3600
DEFAULT_OUTPUT_FORMAT = "summary"
DEFAULT_MAX_RESPONSE_SIZE = 50_000
