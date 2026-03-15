"""Tests for secret masking."""

from __future__ import annotations

from dietmcp.security.masking import collect_secret_values, mask_secrets


class TestMaskSecrets:
    def test_masks_known_secret(self):
        result = mask_secrets(
            "token=ghp_abc123xyz", frozenset({"ghp_abc123xyz"})
        )
        assert result == "token=***"

    def test_ignores_short_secrets(self):
        result = mask_secrets("key=abc", frozenset({"abc"}))
        assert result == "key=abc"  # Too short to mask

    def test_masks_multiple(self):
        result = mask_secrets(
            "a=secret1 b=secret2",
            frozenset({"secret1", "secret2"}),
        )
        assert result == "a=*** b=***"

    def test_no_secrets(self):
        result = mask_secrets("plain text", frozenset())
        assert result == "plain text"

    def test_masks_longer_first(self):
        # "secret_long" contains "secret" as substring
        result = mask_secrets(
            "val=secret_long",
            frozenset({"secret_long", "secret"}),
        )
        # The longer match should be replaced first
        assert "secret_long" not in result

    def test_multiline(self):
        text = "line1: ghp_token123\nline2: ghp_token123"
        result = mask_secrets(text, frozenset({"ghp_token123"}))
        assert "ghp_token123" not in result
        assert result.count("***") == 2


class TestCollectSecretValues:
    def test_identifies_token(self):
        secrets = collect_secret_values({"GITHUB_TOKEN": "ghp_abc123"})
        assert "ghp_abc123" in secrets

    def test_identifies_key(self):
        secrets = collect_secret_values({"API_KEY": "sk-abc123"})
        assert "sk-abc123" in secrets

    def test_identifies_password(self):
        secrets = collect_secret_values({"DB_PASSWORD": "p@ssw0rd"})
        assert "p@ssw0rd" in secrets

    def test_ignores_non_secret(self):
        secrets = collect_secret_values({"APP_NAME": "myapp"})
        assert len(secrets) == 0

    def test_ignores_short_values(self):
        secrets = collect_secret_values({"API_KEY": "ab"})
        assert len(secrets) == 0

    def test_case_insensitive_key(self):
        secrets = collect_secret_values({"github_token": "ghp_abc123"})
        assert "ghp_abc123" in secrets
