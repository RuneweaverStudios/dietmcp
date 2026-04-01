"""URL validation to prevent SSRF attacks."""

from urllib.parse import urlparse
import ipaddress
import logging

logger = logging.getLogger(__name__)

# Blocked private IP ranges
BLOCKED_RANGES = [
    "127.0.0.0/8",      # Loopback
    "10.0.0.0/8",       # Private Class A
    "172.16.0.0/12",    # Private Class B
    "192.168.0.0/16",   # Private Class C
    "169.254.0.0/16",   # Link-local
    "0.0.0.0/8",        # Current network
]

BLOCKED_HOSTNAMES = [
    "localhost",
    "::1",
    "0.0.0.0",
]

BLOCKED_METADATA_ENDPOINTS = [
    "169.254.169.254",  # AWS/GCP/Azure metadata
]


def validate_url(url: str) -> None:
    """Validate URL is not pointing to internal/private network.

    Raises:
        ValueError: If URL is blocked (private IP, localhost, metadata endpoint)
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    # File URLs are allowed (no hostname)
    if parsed.scheme == "file":
        logger.info(f"URL validation passed (file scheme): {url}")
        return

    if not hostname:
        logger.warning(f"URL validation failed: {url} - Invalid URL: no hostname")
        raise ValueError(f"Invalid URL: no hostname: {url}")

    # Check blocked hostnames
    if hostname.lower() in BLOCKED_HOSTNAMES:
        logger.warning(f"URL validation failed: {url} - Blocked hostname: {hostname}")
        raise ValueError(f"Blocked hostname: {hostname}")

    # Check metadata endpoints
    if hostname in BLOCKED_METADATA_ENDPOINTS:
        logger.warning(f"URL validation failed: {url} - Blocked cloud metadata endpoint: {hostname}")
        raise ValueError(f"Blocked cloud metadata endpoint: {hostname}")

    # Check IP ranges BEFORE checking scheme (to catch private IPs even over HTTPS)
    # Only check if hostname is an IP address
    # Check IP ranges BEFORE checking scheme (to catch private IPs even over HTTPS)
    # Check if hostname is an IP address and validate it
    ip_blocked = False
    try:
        ip = ipaddress.ip_address(hostname)
        # This is an IP address
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            logger.warning(f"URL validation failed: {url} - Blocked private IP: {hostname}")
            ip_blocked = True
    except ValueError:
        # Not an IP address (hostname), continue to scheme check
        pass

    if ip_blocked:
        raise ValueError(f"Blocked private IP: {hostname}")

    # Require HTTPS for remote URLs
    if parsed.scheme not in ["https", "file"]:
        logger.warning(f"URL validation failed: {url} - Blocked insecure scheme: {parsed.scheme}")
        raise ValueError(f"Blocked insecure scheme: {parsed.scheme} (require HTTPS)")

    logger.info(f"URL validation passed: {url}")
