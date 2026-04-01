"""Tests for URL validator SSRF protection."""

import pytest
from dietmcp.security.url_validator import validate_url


class TestURLValidator:
    """Test URL validation for SSRF protection."""

    def test_valid_https_url(self):
        """Valid HTTPS URLs should pass validation."""
        validate_url("https://api.example.com/endpoint")
        validate_url("https://github.com/austindixson/dietmcp")
        validate_url("https://api.public.com/v1/resource")

    def test_valid_file_url(self):
        """File URLs should pass validation."""
        # File URLs with no hostname are allowed
        validate_url("file:///path/to/spec.yaml")
        validate_url("file:///Users/ghost/Desktop/spec.json")

    def test_block_localhost(self):
        """Localhost should be blocked."""
        with pytest.raises(ValueError, match="Blocked hostname"):
            validate_url("http://localhost:8080")

        with pytest.raises(ValueError, match="Blocked hostname"):
            validate_url("https://localhost/api")

    def test_block_loopback_ip(self):
        """Loopback IPs should be blocked."""
        # Even with HTTPS, loopback should be blocked
        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://127.0.0.1:8080")

        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://127.0.0.1/api")

    def test_block_private_class_a(self):
        """Private Class A (10.0.0.0/8) should be blocked."""
        # Even with HTTPS, private IPs should be blocked
        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://10.0.0.1:8080")

        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://10.255.255.255/api")

    def test_block_private_class_b(self):
        """Private Class B (172.16.0.0/12) should be blocked."""
        # Even with HTTPS, private IPs should be blocked
        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://172.16.0.1:8080")

        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://172.31.255.255/api")

    def test_block_private_class_c(self):
        """Private Class C (192.168.0.0/16) should be blocked."""
        # Even with HTTPS, private IPs should be blocked
        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://192.168.0.1:8080")

        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://192.168.255.255/api")

    def test_block_link_local(self):
        """Link-local (169.254.0.0/16) should be blocked."""
        # Even with HTTPS, link-local should be blocked
        with pytest.raises(ValueError, match="Blocked private IP"):
            validate_url("https://169.254.1.1:8080")

    def test_block_cloud_metadata_endpoints(self):
        """Cloud metadata endpoints should be blocked."""
        with pytest.raises(ValueError, match="Blocked cloud metadata endpoint"):
            validate_url("http://169.254.169.254/latest/meta-data/")

        with pytest.raises(ValueError, match="Blocked cloud metadata endpoint"):
            validate_url("https://169.254.169.254/api")

    def test_block_ipv6_localhost(self):
        """IPv6 localhost (::1) should be blocked."""
        with pytest.raises(ValueError, match="Blocked hostname"):
            validate_url("http://[::1]:8080")

    def test_block_ipv4_zero(self):
        """IPv4 0.0.0.0 should be blocked."""
        with pytest.raises(ValueError, match="Blocked hostname"):
            validate_url("http://0.0.0.0:8080")

    def test_block_insecure_http(self):
        """HTTP (non-HTTPS) should be blocked for remote URLs."""
        with pytest.raises(ValueError, match="Blocked insecure scheme"):
            validate_url("http://api.example.com/endpoint")

        with pytest.raises(ValueError, match="Blocked insecure scheme"):
            validate_url("http://github.com/austindixson/dietmcp")

    def test_invalid_url_no_hostname(self):
        """URLs without hostname should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid URL: no hostname"):
            validate_url("not-a-url")

    def test_valid_public_ip(self):
        """Public IP addresses should pass validation with HTTPS."""
        validate_url("https://1.1.1.1/api")
        validate_url("https://8.8.8.8/endpoint")
        validate_url("https://93.184.216.34")  # example.com

    def test_ipv6_public_address(self):
        """Public IPv6 addresses should pass validation with HTTPS."""
        validate_url("https://[2001:4860:4860::8888]/dns")
        validate_url("https://[2606:2800:220:1:248:1893:25c8:1946]/")  # example.com

    def test_url_with_path_and_query(self):
        """URLs with paths and query parameters should work."""
        validate_url("https://api.example.com/v1/resource?id=123")
        validate_url("https://api.example.com/path/to/resource?param=value&other=123")

    def test_url_with_port(self):
        """URLs with custom ports should work."""
        validate_url("https://api.example.com:8443/endpoint")
        validate_url("https://api.example.com:9443/api/v1/resource")

    def test_case_insensitive_hostname_check(self):
        """Hostname blocking should be case-insensitive."""
        with pytest.raises(ValueError, match="Blocked hostname"):
            validate_url("https://LOCALHOST/api")

        with pytest.raises(ValueError, match="Blocked hostname"):
            validate_url("https://LoCaLhOsT:8080")
