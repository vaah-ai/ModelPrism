"""Unit tests for the crypto utility module."""

from __future__ import annotations

from uuid import UUID

from app.utils.crypto import (
    TOKEN_PREFIX,
    generate_agent_id,
    generate_token,
    get_token_prefix,
    hash_token,
    verify_token,
)


class TestGenerateToken:
    """Tests for token generation."""

    def test_has_mp_prefix(self) -> None:
        token = generate_token()
        assert token.startswith(TOKEN_PREFIX), f"Expected '{TOKEN_PREFIX}' prefix"

    def test_minimum_length(self) -> None:
        token = generate_token()
        assert len(token) >= 45, f"Token too short: {len(token)}"

    def test_is_urlsafe(self) -> None:
        token = generate_token()
        # mp_ prefix strip, the remaining should be base64url chars only
        raw = token[len(TOKEN_PREFIX) :]
        assert all(c.isalnum() or c in "-_" for c in raw), (
            f"Token contains non-URL-safe characters: {raw}"
        )

    def test_generates_unique_tokens(self) -> None:
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100, "Tokens should be unique"


class TestHashToken:
    """Tests for SHA-256 hashing."""

    def test_returns_hex_string(self) -> None:
        digest = hash_token("mp_test-token-123")
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex length

    def test_deterministic(self) -> None:
        token = generate_token()
        h1 = hash_token(token)
        h2 = hash_token(token)
        assert h1 == h2

    def test_different_tokens_different_hashes(self) -> None:
        h1 = hash_token("mp_token_a")
        h2 = hash_token("mp_token_b")
        assert h1 != h2


class TestGetTokenPrefix:
    """Tests for prefix extraction."""

    def test_returns_first_8_chars(self) -> None:
        token = "mp_abcdefghijklmnop"
        prefix = get_token_prefix(token)
        assert prefix == "mp_abcde"
        assert len(prefix) == 8

    def test_returns_string(self) -> None:
        token = generate_token()
        prefix = get_token_prefix(token)
        assert isinstance(prefix, str)
        assert len(prefix) == 8


class TestVerifyToken:
    """Tests for constant-time token verification."""

    def test_valid_token(self) -> None:
        token = generate_token()
        expected_hash = hash_token(token)
        assert verify_token(token, expected_hash) is True

    def test_invalid_token(self) -> None:
        token = generate_token()
        other_hash = hash_token("mp_different-token")
        assert verify_token(token, other_hash) is False

    def test_wrong_token(self) -> None:
        token = generate_token()
        expected_hash = hash_token(token)
        assert verify_token("mp_wrong-token", expected_hash) is False


class TestGenerateAgentId:
    """Tests for agent ID generation."""

    def test_has_ag_prefix(self) -> None:
        agent_id = generate_agent_id(UUID("00000000-0000-0000-0000-000000000001"))
        assert agent_id.startswith("ag_")

    def test_is_string(self) -> None:
        agent_id = generate_agent_id(UUID("00000000-0000-0000-0000-000000000001"))
        assert isinstance(agent_id, str)
        assert len(agent_id) > 3  # "ag_" + at least 1 char

    def test_different_uuids_different_ids(self) -> None:
        id1 = generate_agent_id(UUID("00000000-0000-0000-0000-000000000001"))
        id2 = generate_agent_id(UUID("00000000-0000-0000-0000-000000000002"))
        assert id1 != id2

    def test_deterministic(self) -> None:
        uuid_obj = UUID("550e8400-e29b-41d4-a716-446655440000")
        id1 = generate_agent_id(uuid_obj)
        id2 = generate_agent_id(uuid_obj)
        assert id1 == id2
