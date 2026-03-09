"""
RevTown API - FastAPI Application Entry Point

"Kubernetes for GTM Agents" — An autonomous go-to-market execution platform.
"""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import settings
from apps.api.middleware.error_handler import RevTownException
from apps.api.routers import (
    approval,
    auth,
    beads,
    billing,
    campaigns,
    mayor,
    neurometric,
    orgs,
    plugins,
    polecats,
    webhooks,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.is_production else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    logger.info(
        "Starting RevTown API",
        mode=settings.revtown_mode,
        env=settings.revtown_env,
    )

    # Startup tasks
    # - Initialize database connections
    # - Connect to Temporal
    # - Initialize Kafka consumers
    # - Start Deacon background tasks

    yield

    # Shutdown tasks
    logger.info("Shutting down RevTown API")


# Create FastAPI application
app = FastAPI(
    title="RevTown API",
    description="Kubernetes for GTM Agents — An autonomous go-to-market execution platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(RevTownException)
async def revtown_exception_handler(request: Request, exc: RevTownException):
    """Handle RevTown-specific exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "bead_id": exc.bead_id,
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )


# =============================================================================
# API Routers
# =============================================================================

# Core Bead operations
app.include_router(beads.router, prefix="/api/v1/beads", tags=["Beads"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])

# Mayor (conversational campaign orchestration)
app.include_router(mayor.router, prefix="/api/v1/mayor", tags=["Mayor"])

# Polecat execution
app.include_router(polecats.router, prefix="/api/v1/polecats", tags=["Polecats"])

# Approval workflow
app.include_router(approval.router, prefix="/api/v1/approval", tags=["Approval"])

# Neurometric (model registry)
app.include_router(neurometric.router, prefix="/api/v1/neurometric", tags=["Neurometric"])

# Plugins
app.include_router(plugins.router, prefix="/api/v1/plugins", tags=["Plugins"])

# Webhooks
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])

# Organization management (API keys, members - available in all modes)
app.include_router(orgs.router, prefix="/api/v1/orgs", tags=["Organizations"])

# SaaS-only routes (auth, billing)
if settings.is_saas:
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": settings.revtown_mode,
        "env": settings.revtown_env,
    }


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "RevTown API",
        "version": "0.1.0",
        "description": "Kubernetes for GTM Agents",
        "docs": "/docs" if settings.debug else None,
    }


# =============================================================================
# CLI Entry Point
# =============================================================================


def run():
    """Run the API server (for CLI entry point)."""
    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
