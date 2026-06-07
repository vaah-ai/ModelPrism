"""ModelPrism Backend — FastAPI Application Entry Point.

This module creates and configures the FastAPI application with:
- Async lifespan management (PostgreSQL + Redis)
- CORS middleware
- Correlation ID middleware
- Prometheus metrics endpoint
- Health check endpoint
- Global exception handlers
- Signal handlers for graceful shutdown

Usage::

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from pydantic import ValidationError
from sqlalchemy import text

from app.api import api_router
from app.config import settings
from app.database import close_db, engine
from app.logging_config import setup_logging
from app.middleware.correlation import CorrelationIDMiddleware
from app.redis import close_redis, init_redis, redis_client, verify_redis_connection
from app.services.agent_manager import agent_registry
from app.services.downsampler import run_downsampler
from app.services.metric_service import metric_service, run_flush_loop
from app.ws.agent_ws import router as agent_ws_router

logger = logging.getLogger(__name__)

_shutting_down = False


def _handle_signal(signum: int, frame: object) -> None:
    """Handle termination signals by setting the shutdown flag.

    uvicorn's event loop will pick this up and trigger the lifespan
    exit path, which runs close_db and close_redis.
    """
    global _shutting_down
    if _shutting_down:
        # Second signal — force immediate exit
        logger.warning("Forced shutdown (signal %d)", signum)
        os._exit(1)
    _shutting_down = True
    logger.info("Shutdown requested (signal %d) — draining connections...", signum)
    # Restore default handler so a second signal forces exit
    signal.signal(signum, signal.SIG_DFL)


def _register_signal_handlers() -> None:
    """Register signal handlers for graceful shutdown."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize services on startup, clean up on shutdown."""

    # ---- Startup ----
    setup_logging()
    _register_signal_handlers()
    logger.info(
        "Starting ModelPrism Backend v%s (environment=%s, cloud_mode=%s)",
        settings.version,
        settings.environment,
        settings.cloud_mode,
    )

    # Initialize database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_host = (
            str(settings.database_url).split("@")[-1]
            if "@" in str(settings.database_url)
            else "unknown"
        )
        logger.info("Database connected: %s", db_host)
    except Exception:
        logger.exception("Failed to connect to database")
        os._exit(1)

    # Initialize Redis (non-fatal if unavailable)
    redis_available = False
    try:
        await init_redis()
        if await verify_redis_connection():
            redis_available = True
            logger.info("Redis connected")
        else:
            logger.warning("Redis PING failed — running in degraded mode")
    except Exception:
        logger.warning(
            "Redis unavailable — running in degraded mode (no rate-limiting, no pub/sub)"
        )

    # Log startup banner
    db_host = (
        str(settings.database_url).split("@")[-1].split(":")[0]
        if "@" in str(settings.database_url)
        else "unknown"
    )
    redis_port = (
        str(settings.redis_url).split(":")[-1].split("/")[0]
        if ":" in str(settings.redis_url)
        else "unknown"
    )
    logger.info("ModelPrism Backend started — %s:%s", db_host, redis_port)
    if redis_available:
        logger.info("Redis available — full functionality enabled")
    else:
        logger.warning("Redis NOT available — degraded mode (rate-limiting and pub/sub disabled)")

    # Inject Redis client into metric service for live queries
    metric_service.set_redis(redis_client)

    # Start the metric flush background worker (every 5 seconds)
    _flush_task = asyncio.create_task(run_flush_loop(metric_service))
    logger.info("Metric flush loop started (every 5s)")

    # Start the metric downsampling background worker (every 60 seconds)
    _downsampler_task = asyncio.create_task(run_downsampler())
    logger.info("Downsampler background worker started")

    yield  # Application runs here

    # ---- Shutdown ----
    logger.info("Shutting down ModelPrism Backend...")
    # Cancel the metric flush loop
    _flush_task.cancel()
    try:
        await _flush_task
    except asyncio.CancelledError:
        pass

    # Cancel the downsampler background task
    _downsampler_task.cancel()
    try:
        await _downsampler_task
    except asyncio.CancelledError:
        pass
    # Notify all connected agents of graceful shutdown
    try:
        notified = await agent_registry.broadcast_shutdown(
            reconnect_delay_seconds=settings.ws_reconnect_delay_seconds,
        )
        if notified:
            logger.info("Sent shutdown notification to %d agent(s)", notified)

            await asyncio.sleep(min(10, settings.ws_reconnect_delay_seconds))
    except Exception:
        logger.warning("Error during agent shutdown broadcast")
    await close_db()
    await close_redis()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="ModelPrism API",
    description="ModelPrism — Open Source GPU Inference Platform",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# --- Middleware ---

# CORS — allow dashboard origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID for request tracing
app.add_middleware(CorrelationIDMiddleware)

# --- Prometheus Metrics ---
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# --- API Routes ---
app.include_router(api_router, prefix="/api")

# --- WebSocket Routes ---
app.include_router(agent_ws_router)

# --- Health Check ---


@app.get("/api/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint.

    Returns the status of the application and its dependencies.
    """
    redis_ok = await verify_redis_connection()
    return {
        "status": "ok" if redis_ok else "degraded",
        "database": "connected",
        "redis": "connected" if redis_ok else "disconnected",
        "version": settings.version,
    }


# --- Global Exception Handlers ---


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with a consistent JSON structure."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
            },
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with a consistent JSON structure."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Validation error",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler to prevent stack traces in production."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
            },
        },
    )
