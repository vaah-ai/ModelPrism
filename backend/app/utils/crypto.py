"""Cryptographic utilities for agent token management.

Provides token generation, hashing (SHA-256), prefix extraction,
and constant-time verification.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

TOKEN_PREFIX = "mp_"


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
