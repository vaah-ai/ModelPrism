"""Enum types for ORM models.

PostgreSQL native ENUM types are created via Alembic migrations.
These Python enums are used for type safety in model definitions.
"""

from __future__ import annotations

import enum


class AgentStatus(enum.StrEnum):
    """Agent connection status."""

    ONLINE = "online"
    OFFLINE = "offline"


class TokenStatus(enum.StrEnum):
    """Agent registration token lifecycle status."""

    PENDING = "pending"
    CLAIMED = "claimed"
    EXPIRED = "expired"


class LogLevel(enum.StrEnum):
    """Log severity levels matching standard logging conventions."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class MetricTier(enum.StrEnum):
    """Metric retention tiers identifying the downsampling window.

    Each tier maps to a specific aggregation interval and retention period:
    - raw:  2s intervals, retained 24h
    - t10s: 10s intervals, retained 7d
    - t1m:  1m intervals, retained 30d
    - t10m: 10m intervals, retained 90d
    - t1h:  1h intervals, retained 1y
    - t6h:  6h intervals, retained indefinitely
    """

    RAW = "raw"
    T10S = "t10s"
    T1M = "t1m"
    T10M = "t10m"
    T1H = "t1h"
    T6H = "t6h"
