"""Metrics API routes.

Provides the historical metric query endpoint consumed by the
dashboard's time-range selector and uPlot charts.

Uses a flat JSON response format (not JSON:API) for optimal chart
performance — the dashboard features heavily on real-time data
rendering and avoids JSON:API envelope overhead for metric data.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.metric_service import (
    metric_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Supported range values
VALID_RANGES = frozenset(
    {
        "live",
        "5m",
        "15m",
        "1h",
        "6h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1M",
        "3M",
        "6M",
        "1y",
    }
)

DEFAULT_RANGE = "1h"


@router.get("/{agent_id}")
async def get_metrics(
    agent_id: UUID,
    range: str = Query(
        default=DEFAULT_RANGE,
        description="Time range for metric query",
    ),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Get historical metrics for a single agent.

    Query parameters:
    - ``range``: one of ``live``, ``5m``, ``15m``, ``1h``, ``6h``,
      ``12h``, ``1d``, ``3d``, ``1w``, ``1M``, ``3M``, ``6M``, ``1y``
      (default: ``1h``)

    Returns a flat JSON object with ``agent_id``, ``range``, ``count``,
    and ``rows`` containing the metric data.

    The ``live`` range reads from Redis only — no database query.
    All other ranges query the ``agent_metrics`` table.
    """
    # Validate range parameter
    if range not in VALID_RANGES:
        valid = sorted(VALID_RANGES)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Invalid range '{range}'. Valid options: {', '.join(valid)}",
                "valid_ranges": list(valid),
            },
        )

    # Live range → Redis (no DB needed)
    if range == "live":
        rows = await metric_service.query_metrics(agent_id, "live")
        return {
            "agent_id": str(agent_id),
            "range": "live",
            "count": len(rows),
            "rows": rows,
        }

    # Historical range → DB
    try:
        rows = await metric_service.query_metrics(
            agent_id,
            range,
            session=session,
        )
    except Exception:
        logger.exception("Failed to query metrics for agent %s", agent_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query metrics",
        )

    return {
        "agent_id": str(agent_id),
        "range": range,
        "count": len(rows),
        "rows": rows,
    }
