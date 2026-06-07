"""ModelPrism Backend — FastAPI Application Entry Point.

This module creates and configures the FastAPI application with:
- Async lifespan management (PostgreSQL + Redis)
- CORS middleware
- Correlation ID middleware
- Prometheus metrics endpoint
- Health check endpoint
- Global exception handlers

Usage::

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import sys
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
from app.redis import close_redis, init_redis, verify_redis_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize services on startup, clean up on shutdown."""

    # ---- Startup ----
    setup_logging()
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
        sys.exit(1)

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

    yield  # Application runs here

    # ---- Shutdown ----
    logger.info("Shutting down ModelPrism Backend...")
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
