"""OpenAPI security scheme models for API keys, OAuth 2.0, etc."""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


class SecuritySchemeType(str, Enum):
    """OpenAPI security scheme types."""
    API_KEY = "apiKey"
    HTTP = "http"
    OAUTH2 = "oauth2"
    OPEN_ID_CONNECT = "openIdConnect"
    MUTUAL_TLS = "mutualTLS"


@dataclass(frozen=True)
class SecurityScheme:
    """OpenAPI security scheme configuration."""

    name: str
    """Security scheme identifier (e.g., "api_key", "bearer")."""

    type: SecuritySchemeType
    """Type of security scheme."""

    description: Optional[str] = None
    """Description of the security scheme."""

    in_: Optional[str] = None
    """Location for apiKey (header, query, cookie)."""

    scheme: Optional[str] = None
    """HTTP scheme (bearer, basic, digest, etc.)."""

    bearer_format: Optional[str] = None
    """Format for bearer tokens (e.g., "JWT")."""

    flows: Optional[Dict[str, Any]] = None
    """OAuth2 flow configurations."""

    scopes: Optional[List[str]] = None
    """Available OAuth scopes."""

    open_id_connect_url: Optional[str] = None
    """OpenID Connect URL."""

    def get_auth_headers(self, credentials: Dict[str, str]) -> Dict[str, str]:
        """Generate HTTP headers for this security scheme.

        Args:
            credentials: Dictionary of credential values (e.g., {"api_key": "xyz"})

        Returns:
            Dictionary of HTTP headers
        """
        headers: Dict[str, str] = {}

        if self.type == SecuritySchemeType.API_KEY:
            if self.in_ == "header":
                key_name = self.scheme or self.name
                if key_name in credentials:
                    headers[key_name] = credentials[key_name]
                else:
                    # Default to Authorization header if no scheme specified
                    if self.name.lower() in ["bearer", "authorization"]:
                        headers["Authorization"] = credentials.get("api_key", credentials.get("token", ""))
                    else:
                        headers[key_name] = credentials.get("api_key", credentials.get("token", ""))
            elif self.in_ == "query":
                # Query parameters are handled by request builder
                pass
            elif self.in_ == "cookie":
                headers["Cookie"] = f"{self.name}={credentials.get('api_key', credentials.get('token', ''))}"

        elif self.type == SecuritySchemeType.HTTP:
            if self.scheme == "bearer":
                token = credentials.get("bearer_token", credentials.get("token", ""))
                headers["Authorization"] = f"Bearer {token}"
            elif self.scheme == "basic":
                import base64
                username = credentials.get("username", "")
                password = credentials.get("password", "")
                credentials_str = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials_str}"

        elif self.type == SecuritySchemeType.OAUTH2:
            # OAuth2 flow would require access token
            token = credentials.get("access_token", "")
            headers["Authorization"] = f"Bearer {token}"

        return headers
