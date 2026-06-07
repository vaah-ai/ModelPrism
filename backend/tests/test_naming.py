"""Unit tests for the agent naming utility."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.utils.naming import generate_name, generate_unique_name


class TestGenerateName:
    """Tests for synchronous name generation."""

    def test_returns_string(self) -> None:
        name = generate_name()
        assert isinstance(name, str)

    def test_pattern_adjective_animal_number(self) -> None:
        name = generate_name()
        parts = name.split("-")
        assert len(parts) >= 3, f"Expected at least 3 parts, got: {parts}"
        # Last part should be a number
        assert parts[-1].isdigit(), f"Last part should be a number, got: {parts[-1]}"

    def test_generates_unique_values(self) -> None:
        names = {generate_name() for _ in range(100)}
        assert len(names) > 50, "Expected at least 50 unique names in 100 tries"

    def test_no_special_characters(self) -> None:
        name = generate_name()
        # Only lowercase letters, hyphens, and digits
        assert name.replace("-", "").isalnum(), f"Name contains invalid characters: {name}"
        assert name.islower(), f"Name should be lowercase: {name}"


class TestGenerateUniqueName:
    """Tests for async unique name generation with DB check."""

    @pytest.mark.asyncio
    async def test_returns_string_when_unique(self) -> None:
        mock_db = AsyncMock()
        mock_db.execute.return_value = AsyncMock(spec=["scalar_one_or_none"])
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.utils.naming.select") as mock_select:
            mock_select.return_value.where.return_value = "select_query"
            name = await generate_unique_name(mock_db)

        assert isinstance(name, str)
        assert name.count("-") >= 2

    @pytest.mark.asyncio
    async def test_retries_on_collision(self) -> None:
        """First 2 names collide, 3rd is unique."""
        mock_db = AsyncMock()

        result_with_data = AsyncMock(spec=["scalar_one_or_none"])
        result_with_data.scalar_one_or_none.return_value = "existing-agent"
        result_empty = AsyncMock(spec=["scalar_one_or_none"])
        result_empty.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [
            result_with_data,
            result_with_data,
            result_empty,
        ]

        with patch("app.utils.naming.select") as mock_select:
            mock_select.return_value.where.return_value = "select_query"
            name = await generate_unique_name(mock_db)

        assert isinstance(name, str)

    @pytest.mark.asyncio
    async def test_raises_on_max_attempts(self) -> None:
        """All attempts collide — should raise RuntimeError."""
        mock_db = AsyncMock()
        mock_result = AsyncMock(spec=["scalar_one_or_none"])
        mock_result.scalar_one_or_none.return_value = "always-existing"
        mock_db.execute.return_value = mock_result

        with patch("app.utils.naming.select") as mock_select:
            mock_select.return_value.where.return_value = "select_query"
            with pytest.raises(RuntimeError, match="Could not generate a unique agent name"):
                await generate_unique_name(mock_db, max_attempts=3)

    @pytest.mark.asyncio
    async def test_passes_max_attempts(self) -> None:
        """Verify the max_attempts parameter is passed."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = AsyncMock(spec=["scalar_one_or_none"])
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with patch("app.utils.naming.select") as mock_select:
            mock_select.return_value.where.return_value = "select_query"
            with patch(
                "app.utils.naming.generate_name",
                return_value="test-animal-1",
            ):
                name = await generate_unique_name(mock_db, max_attempts=5)
                assert name == "test-animal-1"
