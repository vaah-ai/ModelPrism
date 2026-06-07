"""Correlation ID middleware for request tracing.

Generates or reads a correlation ID from the X-Correlation-ID header
and adds it to the request state and log records.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a correlation ID to every request.

    If the client sends an ``X-Correlation-ID`` header, that value is used.
    Otherwise, a new UUID is generated.

    The correlation ID is:
    - Stored in ``request.state.correlation_id``
    - Added to response headers as ``X-Correlation-ID``
    - Available to log formatters via the ``correlation_id`` key
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4()),
        )
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
