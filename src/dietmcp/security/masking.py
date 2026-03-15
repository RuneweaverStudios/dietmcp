"""Secret masking for logs and error output.

DEV NOTES:
- Secrets are masked by sorting longest-first to prevent partial matches.
  Example: if both "secret" and "secret_long" are secrets, we replace
  "secret_long" first to avoid leaving "***_long" in the output.
- The 4-character minimum prevents false positives on short common strings
  like "key", "api", etc. that appear everywhere in JSON output.
- collect_secret_values uses keyword heuristics (TOKEN, KEY, SECRET, etc.)
  rather than requiring explicit annotation. This catches most real-world
  credential patterns without requiring users to mark secrets manually.
"""

from __future__ import annotations


_MASK = "***"
_MIN_SECRET_LENGTH = 4


def mask_secrets(text: str, secret_values: frozenset[str]) -> str:
    """Replace all occurrences of known secret values with '***'.

    Only masks values that are at least 4 characters long to avoid
    false positives on short common strings.
    """
    result = text
    # Sort by length descending so longer secrets are masked first,
    # preventing partial matches from shorter substrings.
    for secret in sorted(secret_values, key=len, reverse=True):
        if len(secret) >= _MIN_SECRET_LENGTH:
            result = result.replace(secret, _MASK)
    return result


def collect_secret_values(env_dict: dict[str, str]) -> frozenset[str]:
    """Extract values from an env dict that look like secrets.

    Heuristic: keys containing TOKEN, KEY, SECRET, PASSWORD, or CREDENTIAL
    (case-insensitive) are considered secrets.
    """
    secret_keywords = {"token", "key", "secret", "password", "credential", "auth"}
    secrets = set()
    for key, value in env_dict.items():
        key_lower = key.lower()
        if any(kw in key_lower for kw in secret_keywords):
            if len(value) >= _MIN_SECRET_LENGTH:
                secrets.add(value)
    return frozenset(secrets)
