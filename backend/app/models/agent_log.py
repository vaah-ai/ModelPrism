"""AgentLog ORM model.

Structured log entries emitted by agents during operation. Logs are
pushed by the agent via HTTP POST and displayed in the dashboard
log viewer with level filtering and time-range selection.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import LogLevel

if TYPE_CHECKING:
    from app.models.agent import Agent


class AgentLog(Base):
    """A single structured log entry from an agent."""

    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Sequential PK for high-volume log ingestion",
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Log timestamp (set by the agent)",
    )
    level: Mapped[LogLevel] = mapped_column(
        nullable=False,
        comment="Log severity level",
    )
    module: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Source module or component name",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Log message body",
    )
    stack_trace: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional exception stack trace",
    )

    # Relationships
    agent: Mapped[Agent] = relationship(
        "Agent",
        back_populates="logs",
    )

    __table_args__ = (
        Index(
            "ix_agent_logs_agent_ts_level",
            "agent_id",
            "ts",
            "level",
            postgresql_using="btree",
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentLog id={self.id} agent_id={self.agent_id} level='{self.level}'>"
