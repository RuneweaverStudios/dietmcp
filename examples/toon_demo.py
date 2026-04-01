#!/usr/bin/env python3
"""Demonstration of TOON formatter compression performance."""

import json
from dietmcp.formatters.toon_formatter import _encode_toon, _decode_toon

# Example 1: Simple database result
print("=" * 60)
print("Example 1: Database Users")
print("=" * 60)

users = [
    {"id": 1, "name": "Alice Johnson", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "role": "user"},
    {"id": 3, "name": "Charlie Brown", "email": "charlie@example.com", "role": "user"},
    {"id": 4, "name": "Diana Prince", "email": "diana@example.com", "role": "admin"},
]

json_str = json.dumps(users)
toon_str = _encode_toon(users)

print(f"\nOriginal JSON ({len(json_str)} chars):")
print(json_str[:200] + "..." if len(json_str) > 200 else json_str)

print(f"\nTOON encoded ({len(toon_str)} chars):")
print(toon_str)

compression = (1 - len(toon_str) / len(json_str)) * 100
print(f"\nCompression: {compression:.1f}% reduction")

# Verify round-trip
decoded = _decode_toon(toon_str)
assert decoded == users
print("✓ Round-trip successful")

# Example 2: Large keys (more compression)
print("\n" + "=" * 60)
print("Example 2: API Response with Long Keys")
print("=" * 60)

api_data = [
    {
        "user_identifier": "12345",
        "user_display_name": "John Doe",
        "user_email_address": "john@example.com",
        "user_profile_url": "https://example.com/users/12345",
        "user_account_status": "active",
    },
    {
        "user_identifier": "67890",
        "user_display_name": "Jane Smith",
        "user_email_address": "jane@example.com",
        "user_profile_url": "https://example.com/users/67890",
        "user_account_status": "active",
    },
]

json_str2 = json.dumps(api_data)
toon_str2 = _encode_toon(api_data)

print(f"\nOriginal JSON ({len(json_str2)} chars):")
print(json_str2[:200] + "..." if len(json_str2) > 200 else json_str2)

print(f"\nTOON encoded ({len(toon_str2)} chars):")
print(toon_str2)

compression2 = (1 - len(toon_str2) / len(json_str2)) * 100
print(f"\nCompression: {compression2:.1f}% reduction")

# Example 3: Special characters
print("\n" + "=" * 60)
print("Example 3: Special Characters and Escaping")
print("=" * 60)

special_data = [
    {"id": 1, "text": "Hello, world!"},
    {"id": 2, "text": "Key: value"},
    {"id": 3, "text": "Test[brackets]"},
    {"id": 4, "text": "With`backticks`"},
]

toon_str3 = _encode_toon(special_data)
print(f"\nTOON encoded with special characters:")
print(toon_str3)

decoded3 = _decode_toon(toon_str3)
assert decoded3 == special_data
print("✓ Special characters handled correctly")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print("TOON encoding achieves significant compression on:")
print("• Uniform arrays (database results, API responses)")
print("• Data with many/f repetitive keys")
print("• While maintaining lossless reversibility")
