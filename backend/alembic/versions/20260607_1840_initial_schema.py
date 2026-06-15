"""Foundation database schema — Agent Management tables.

Creates all four foundation ORM tables:

- ``agents`` — registered GPU inference agents
- ``agent_tokens`` — two-phase registration tokens
- ``agent_metrics`` — time-series GPU/system/vLLM observations
- ``agent_logs`` — structured agent log entries

Revision ID: 20260607_1840
Revises: None
Create Date: 2026-06-07 18:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260607_1840"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the initial schema migration."""

    # Enable UUID generation extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # --- agents ---
    op.create_table(
        "agents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.Enum("online", "offline", name="agentstatus", create_type=False),
            nullable=False,
            server_default="offline",
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gpu_info", postgresql.JSONB, nullable=True),
        sa.Column("cpu_info", postgresql.JSONB, nullable=True),
        sa.Column("disk_info", postgresql.JSONB, nullable=True),
        sa.Column("os_info", sa.String(255), nullable=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agents_status", "agents", ["status"])
    op.create_index("ix_agents_last_seen_at", "agents", ["last_seen_at"])
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])

    # --- agent_tokens ---
    op.create_table(
        "agent_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("prefix", sa.String(8), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "claimed", "expired", name="tokenstatus", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_tokens_token_hash",
        "agent_tokens",
        ["token_hash"],
    )

    # --- agent_metrics ---
    op.create_table(
        "agent_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tier",
            sa.String(10),
            nullable=False,
            server_default="raw",
        ),
        # GPU metrics
        sa.Column("gpu_util_pct", sa.Float(), nullable=True),
        sa.Column("gpu_mem_used_mb", sa.Float(), nullable=True),
        sa.Column("gpu_temp_c", sa.Float(), nullable=True),
        sa.Column("gpu_power_w", sa.Float(), nullable=True),
        sa.Column("gpu_cache_pct", sa.Float(), nullable=True),
        # vLLM metrics
        sa.Column("running", sa.Integer(), nullable=True),
        sa.Column("waiting", sa.Integer(), nullable=True),
        sa.Column("total_requests", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens_total", sa.Integer(), nullable=True),
        sa.Column("gen_tokens_total", sa.Integer(), nullable=True),
        sa.Column("ttft_p50_ms", sa.Float(), nullable=True),
        sa.Column("ttft_p99_ms", sa.Float(), nullable=True),
        sa.Column("tps", sa.Float(), nullable=True),
        sa.Column("prefix_cache_hit", sa.Float(), nullable=True),
        sa.Column("error_rate", sa.Float(), nullable=True),
        sa.Column("trunc_rate", sa.Float(), nullable=True),
        # System metrics
        sa.Column("ram_used_gb", sa.Float(), nullable=True),
        sa.Column("ram_total_gb", sa.Float(), nullable=True),
        sa.Column("cpu_pct", sa.Float(), nullable=True),
        sa.Column("load_1", sa.Float(), nullable=True),
        sa.Column("load_5", sa.Float(), nullable=True),
        sa.Column("load_15", sa.Float(), nullable=True),
        sa.Column("disk_used_gb", sa.Float(), nullable=True),
        sa.Column("disk_total_gb", sa.Float(), nullable=True),
        sa.Column("disk_pct", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_agent_metrics_agent_ts_tier",
        "agent_metrics",
        ["agent_id", "ts", "tier"],
        postgresql_using="btree",
    )

    # --- agent_logs ---
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "level",
            sa.Enum("debug", "info", "warning", "error", name="loglevel", create_type=False),
            nullable=False,
            server_default="info",
        ),
        sa.Column("module", sa.String(100), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_agent_logs_agent_ts_level",
        "agent_logs",
        ["agent_id", "ts", "level"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Revert the initial schema migration."""

    # Drop tables in reverse dependency order
    op.drop_table("agent_logs")
    op.drop_table("agent_metrics")
    op.drop_table("agent_tokens")
    op.drop_table("agents")

    # Drop enum types
    sa.Enum(name="loglevel").drop(op.get_bind())
    sa.Enum(name="tokenstatus").drop(op.get_bind())
    sa.Enum(name="agentstatus").drop(op.get_bind())

    # Note: pgcrypto extension is NOT dropped — it may be used by other
    # applications in the same database cluster.
