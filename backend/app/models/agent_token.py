"""AgentToken ORM model.

Represents registration tokens used in the two-phase agent registration flow:
1. A token is pre-generated (pending status) with a known prefix
2. The agent claims the token during registration (claimed status)
3. Tokens expire after their configured TTL (expired status)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import TokenStatus

if TYPE_CHECKING:
    from app.models.agent import Agent


class AgentToken(Base):
    """A single-use agent registration token.

    Tokens are created by an admin in the dashboard or via API, then
    provided to the agent installation script to authenticate during
    the two-phase registration process.
    """

    __tablename__ = "agent_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="SHA-256 hash of the full registration token",
    )
    prefix: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="First 8 characters of the token for display/lookup",
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        comment="Agent that claimed this token (null until claimed)",
    )
    status: Mapped[TokenStatus] = mapped_column(
        default=TokenStatus.PENDING,
        nullable=False,
        comment="Current token lifecycle status",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Token expiration timestamp",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    agent: Mapped[Agent | None] = relationship(
        "Agent",
        back_populates="tokens",
    )

    __table_args__ = (Index("ix_agent_tokens_token_hash", "token_hash"),)

    def __repr__(self) -> str:
        return f"<AgentToken id={self.id} prefix='{self.prefix}' status='{self.status}'>"
