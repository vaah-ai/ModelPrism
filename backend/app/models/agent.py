"""Agent ORM model.

Represents a registered GPU-backed agent running on customer hardware.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import AgentStatus

if TYPE_CHECKING:
    from app.models.agent_log import AgentLog
    from app.models.agent_metric import AgentMetric
    from app.models.agent_token import AgentToken


class Agent(Base):
    """A registered GPU inference agent.

    Each row represents a single GPU server that has completed the
    two-phase registration process and can receive commands / push metrics.
    """

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Auto-generated friendly name, e.g. 'cyan-koala-42'",
    )
    hostname: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Server hostname reported by the agent at registration",
    )
    agent_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="SemVer of the installed modelprism-agent package",
    )
    status: Mapped[AgentStatus] = mapped_column(
        default=AgentStatus.OFFLINE,
        nullable=False,
        comment="Current agent connection status",
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last heartbeat or successful communication timestamp",
    )
    gpu_info: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="GPU hardware details (model, count, VRAM per GPU, driver)",
    )
    cpu_info: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="CPU hardware details (model, cores, threads, architecture)",
    )
    disk_info: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Disk information (mounts, total, used, filesystem types)",
    )
    os_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Operating system identifier, e.g. 'Ubuntu 22.04'",
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Optional workspace FK for future multi-tenancy (enforced in M4)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    tokens: Mapped[list[AgentToken]] = relationship(
        "AgentToken",
        back_populates="agent",
        cascade="save-update, merge",
    )
    metrics: Mapped[list[AgentMetric]] = relationship(
        "AgentMetric",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list[AgentLog]] = relationship(
        "AgentLog",
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_agents_status", "status"),
        Index("ix_agents_last_seen_at", "last_seen_at"),
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name='{self.name}' status='{self.status}'>"
