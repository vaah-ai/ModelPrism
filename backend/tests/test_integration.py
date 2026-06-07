"""Integration test scaffold for backend with real PostgreSQL and Redis.

These tests require docker-compose services (PostgreSQL + Redis) to be running.
They are marked with ``pytest.mark.integration`` and are skipped by default.

To run::

    # Start services
    docker compose -f deploy/docker-compose.yml up -d postgres redis

    # Run integration tests
    pytest tests/ -m integration -v

    # Clean up
    docker compose -f deploy/docker-compose.yml down
"""

from __future__ import annotations

import pytest


@pytest.mark.integration()
class TestIntegrationHealth:
    """Integration tests against real PostgreSQL and Redis.

    These tests use the production-style startup sequence:
    1. Initialize settings from .env
    2. Start FastAPI app with lifespan
    3. Verify health endpoint returns correct status
    4. Verify shutdown cleans up connections
    """

    def test_placeholder(self) -> None:
        """Placeholder test — integration tests require a running environment.

        TODO: Implement integration tests when docker-compose is set up:
        - Verify startup connects to PostgreSQL
        - Verify startup connects to Redis
        - Verify health returns ok/connected
        - Verify Redis outage returns degraded
        - Verify shutdown releases DB connections
        - Verify shutdown releases Redis connections
        """
        pass
