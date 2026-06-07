"""Correlation ID middleware for request tracing.

Generates or reads a correlation ID from the X-Correlation-ID header
and adds it to the request state, response headers, and log records.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

# Context variable to hold the current request's correlation ID
# This allows log filters to access it without touching the request object.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIDFilter(logging.Filter):
    """Logging filter that injects the correlation_id into every log record.

    Add this filter to your root logger or handler configuration to
    automatically populate the ``correlation_id`` field in log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        cid = correlation_id_var.get()
        if cid:
            record.correlation_id = cid
        return True


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a correlation ID to every request.

    If the client sends an ``X-Correlation-ID`` header, that value is used.
    Otherwise, a new UUID is generated.

    The correlation ID is:
    - Stored in ``request.state.correlation_id``
    - Added to response headers as ``X-Correlation-ID``
    - Available to log formatters via the ``correlation_id`` key
      (via ``CorrelationIDFilter`` on the root logger)
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
        correlation_id_var.set(correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
