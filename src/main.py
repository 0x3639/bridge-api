"""
Orchestrator API - Main Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.health import router as health_router
from src.api.v1.router import api_router
from src.config import settings
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitExceededError,
)
from src.dependencies import close_db, close_redis, init_db, init_redis
from src.tasks.data_collector import run_initial_collection
from src.tasks.scheduler import setup_scheduler, shutdown_scheduler, start_scheduler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Orchestrator API...")

    await init_db()
    logger.info("Database connection initialized")

    await init_redis()
    logger.info("Redis connection initialized")

    # Set up and start scheduler
    setup_scheduler()
    start_scheduler()
    logger.info("Background scheduler started")

    # Run initial data collection
    try:
        await run_initial_collection()
    except Exception as e:
        logger.warning(f"Initial data collection failed (will retry on schedule): {e}")

    logger.info("Orchestrator API started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Orchestrator API...")

    shutdown_scheduler()
    logger.info("Background scheduler stopped")

    await close_redis()
    logger.info("Redis connection closed")

    await close_db()
    logger.info("Database connection closed")

    logger.info("Orchestrator API shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="API for orchestrator/bridge health monitoring",
    version="1.0.0",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limit header middleware
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next) -> Response:
    """Add rate limit headers to responses."""
    # Initialize rate limit headers storage
    request.state.rate_limit_headers = {}

    response = await call_next(request)

    # Add any rate limit headers that were set
    for key, value in getattr(request.state, "rate_limit_headers", {}).items():
        response.headers[key] = value

    return response


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Add security headers to all responses."""
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RateLimitExceededError)
async def rate_limit_error_handler(request: Request, exc: RateLimitExceededError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


# Include routers
app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_v1_prefix)


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": settings.api_v1_prefix,
    }
