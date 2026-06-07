"""SQLAlchemy ORM models package.

Provides the declarative ``Base`` class that all models inherit from,
and re-exports every model for convenient imports and Alembic autogeneration.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


# Re-exports for Alembic autogeneration — must come after Base definition
from app.models.agent import Agent  # noqa: E402, F401
from app.models.agent_log import AgentLog  # noqa: E402, F401
from app.models.agent_metric import AgentMetric  # noqa: E402, F401
from app.models.agent_token import AgentToken  # noqa: E402, F401
from app.models.enums import (  # noqa: E402, F401
    AgentStatus,
    LogLevel,
    MetricTier,
    TokenStatus,
)
