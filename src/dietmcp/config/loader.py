"""Configuration loading and server resolution."""

from __future__ import annotations

import json
from pathlib import Path

from dietmcp.config.defaults import CONFIG_DIR, CONFIG_FILE, DEFAULT_CACHE_TTL, ENV_SEARCH_PATHS
from dietmcp.config.schema import DietMcpConfig, ServerEntry
from dietmcp.models.server import ServerConfig
from dietmcp.security.credentials import collect_env, resolve_template


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


def load_config(config_path: Path | None = None) -> DietMcpConfig:
    """Load and validate the configuration file.

    Args:
        config_path: Override path to the config file.
                     Defaults to ~/.config/dietmcp/servers.json.

    Returns:
        Validated DietMcpConfig instance.

    Raises:
        ConfigError: If the file is missing, unreadable, or invalid.
    """
    path = config_path or CONFIG_FILE
    if not path.is_file():
        raise ConfigError(
            f"Config file not found: {path}\n"
            f"Run 'dietmcp config init' to create one."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        return DietMcpConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigError(f"Invalid config structure in {path}: {exc}") from exc


def resolve_server(
    name: str,
    entry: ServerEntry,
    global_defaults: DietMcpConfig | None = None,
) -> ServerConfig:
    """Resolve a ServerEntry into a fully-interpolated ServerConfig.

    Replaces ${VAR} placeholders in env values, headers, and url fields.

    .env search order (later wins):
    1. os.environ (shell env)
    2. Global config dir .env (~/.config/dietmcp/.env or platform equivalent)
    3. Project root .env (where dietmcp package lives)
    4. CWD .env (current working directory)
    5. Custom env_file from config defaults
    """
    dotenv_paths = list(ENV_SEARCH_PATHS)
    # CWD .env (may differ from project root)
    cwd_env = Path.cwd() / ".env"
    if cwd_env not in dotenv_paths:
        dotenv_paths.append(cwd_env)
    # Custom env_file from config
    if global_defaults and global_defaults.defaults.env_file:
        custom = Path(global_defaults.defaults.env_file).expanduser()
        dotenv_paths.append(custom)
    env = collect_env(dotenv_paths)

    resolved_env = {}
    for k, v in entry.env.items():
        resolved_env[k] = resolve_template(v, env)

    resolved_headers = {}
    for k, v in entry.headers.items():
        resolved_headers[k] = resolve_template(v, env)

    resolved_url = None
    if entry.url:
        resolved_url = resolve_template(entry.url, env)

    cache_ttl = entry.cache_ttl or (
        global_defaults.defaults.cache_ttl_seconds if global_defaults else DEFAULT_CACHE_TTL
    )

    return ServerConfig(
        name=name,
        command=entry.command,
        args=tuple(entry.args),
        env=resolved_env,
        headers=resolved_headers,
        url=resolved_url,
        cache_ttl=cache_ttl,
    )


def get_server_config(
    server_name: str, config: DietMcpConfig
) -> ServerConfig:
    """Look up and resolve a server by name.

    Raises:
        ConfigError: If the server name is not found.
    """
    entry = config.mcpServers.get(server_name)
    if entry is None:
        available = ", ".join(sorted(config.mcpServers.keys())) or "(none)"
        raise ConfigError(
            f"Server '{server_name}' not found. Available: {available}"
        )
    return resolve_server(server_name, entry, config)


def list_server_names(config: DietMcpConfig) -> list[str]:
    """Return sorted list of all configured server names across all protocols."""
    all_servers = set(config.mcpServers.keys())
    all_servers.update(config.openapiServers.keys())
    all_servers.update(config.graphqlServers.keys())
    return sorted(all_servers)


def detect_protocol(server_name: str, config: DietMcpConfig) -> str:
    """Auto-detect protocol from server name.

    Args:
        server_name: Name of the server to look up.
        config: Full application configuration.

    Returns:
        Protocol name: "mcp", "openapi", or "graphql".

    Raises:
        ConfigError: If server name is not found in any protocol.
    """
    if server_name in config.mcpServers:
        return "mcp"
    elif server_name in config.openapiServers:
        return "openapi"
    elif server_name in config.graphqlServers:
        return "graphql"
    else:
        available = list_server_names(config)
        if available:
            raise ConfigError(
                f"Server '{server_name}' not found. Available: {', '.join(available)}"
            )
        else:
            raise ConfigError(
                f"Server '{server_name}' not found. No servers configured.\n"
                f"Run 'dietmcp config init' to get started."
            )


def create_default_config(path: Path | None = None) -> Path:
    """Write a default config file with example servers.

    Returns the path to the created file.
    """
    target = path or CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    default = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            },
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"},
            },
        },
        "openapiServers": {
            "petstore": {
                "url": "https://petstore3.swagger.io/api/v3/openapi.json",
                "auth": {"header": "X-API-Key: ${PETSTORE_API_KEY}"},
                "baseUrl": "https://petstore3.swagger.io/api/v3",
            },
        },
        "graphqlServers": {
            "github": {
                "url": "https://api.github.com/graphql",
                "auth": {"header": "Authorization: Bearer ${GITHUB_TOKEN}"},
            },
        },
        "defaults": {
            "cacheTtlSeconds": 3600,
            "outputFormat": "summary",
            "maxResponseSize": 50000,
        },
    }

    target.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
    return target
