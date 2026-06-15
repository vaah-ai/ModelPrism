"""Cryptographic utilities for agent token management and ID generation.

Provides token generation, hashing (SHA-256), prefix extraction,
constant-time verification, and agent ID generation.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from uuid import UUID

TOKEN_PREFIX = "mp_"
AGENT_ID_PREFIX = "ag_"


def generate_token() -> str:
    """Generate a cryptographically secure registration token.

    The token uses a ``mp_`` prefix followed by 43 URL-safe base64
    characters (256 bits of entropy), for a total length of 46 characters.

    Returns:
        A token string like ``"mp_abc123..."``.
    """
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token.

    Args:
        token: The raw token string.

    Returns:
        A 64-character lowercase hex string.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_token_prefix(token: str) -> str:
    """Extract the first 8 characters of a token for display purposes.

    Args:
        token: The full token string.

    Returns:
        An 8-character prefix string, e.g. ``"mp_abc12"``.
    """
    return token[:8]


def verify_token(token: str, expected_hash: str) -> bool:
    """Verify a token against its stored hash using constant-time comparison.

    Args:
        token: The raw token string to verify.
        expected_hash: The previously computed SHA-256 hex digest.

    Returns:
        True if the token matches the hash, False otherwise.
    """
    computed = hash_token(token)
    return hmac.compare_digest(computed, expected_hash)


_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _uuid_to_base62(uuid_obj: UUID) -> str:
    """Convert a UUID to a compact base-62 string.

    Returns a string of up to 22 characters representing the 128-bit
    UUID value.  The encoding is lossless and produces shorter IDs
    than the standard hex representation.
    """
    value = uuid_obj.int
    if value == 0:
        return "0"
    chars: list[str] = []
    while value > 0:
        value, remainder = divmod(value, 62)
        chars.append(_BASE62_ALPHABET[remainder])
    return "".join(reversed(chars))


def generate_agent_id(uuid_obj: UUID) -> str:
    """Generate a compact, human-friendly agent ID with ``ag_`` prefix.

    The UUID is base-62 encoded for compactness, then prefixed with
    ``ag_``.  Example output: ``"ag_1A2b3C4d5E6f7G8h"``.

    Args:
        uuid_obj: The agent's UUID primary key.

    Returns:
        A string like ``"ag_1A2b3C4d5E6f7G8h"``.
    """
    return AGENT_ID_PREFIX + _uuid_to_base62(uuid_obj)


def _base62_to_int(s: str) -> int:
    """Decode a base-62 string back to an integer."""
    value = 0
    for char in s:
        value = value * 62 + _BASE62_ALPHABET.index(char)
    return value


def parse_agent_id(raw: str) -> UUID:
    """Parse an agent identifier string into a ``UUID``.

    Accepts:
    - A raw UUID string (e.g. ``"550e8400-e29b-41d4-a716-446655440000"``)
    - A compact ``ag_``-prefixed base-62 ID (e.g. ``"ag_1A2b3C4d5E6f7G8h"``)

    Returns:
        The parsed ``UUID``.

    Raises:
        ValueError: If the string cannot be parsed as either format.
    """
    # Strip ag_ prefix if present
    if raw.startswith(AGENT_ID_PREFIX):
        return UUID(int=_base62_to_int(raw[len(AGENT_ID_PREFIX):]))
    # Fall back to standard UUID parsing
    return UUID(raw)
