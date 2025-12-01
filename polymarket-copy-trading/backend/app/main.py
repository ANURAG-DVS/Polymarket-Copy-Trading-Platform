"""
FastAPI application with safe trader module imports.

CRITICAL: Trader routes are imported with try/except to allow app to start
even if trader models have issues during development.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Polymarket Copy Trading API",
    version="1.0.0",
    description="Backend API for Polymarket copy trading platform"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8500",
        "http://localhost:3000",
        "http://localhost:3001",
        settings.FRONTEND_URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core routers (always available)
from app.api.v1.endpoints import health, auth
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])

# SAFE trader router import - only if tables exist
try:
    from app.api.v1.endpoints import traders, trades
    app.include_router(traders.router, prefix="/api/v1/traders", tags=["traders"])
    app.include_router(trades.router, prefix="/api/v1/trades", tags=["trades"])
    logger.info("✅ Trader and Trades routes loaded successfully")
except Exception as e:
    logger.warning(f"⚠️  Trader/Trades routes not loaded: {e}")
    # App continues without trader routes

# Admin router (optional)
try:
    from app.api.v1.endpoints import admin
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    logger.info("✅ Admin routes loaded successfully")
except Exception as e:
    logger.warning(f"⚠️  Admin routes not loaded: {e}")

# WebSocket endpoint (optional)
try:
    from app.api.websocket import websocket_endpoint
    app.add_websocket_route("/ws", websocket_endpoint)
    logger.info("✅ WebSocket endpoint loaded")
except Exception as e:
    logger.warning(f"⚠️  WebSocket not loaded: {e}")


@app.on_event("startup")
async def startup_event():
    """
    Startup tasks.
    
    NOTE: Don't trigger trader fetch on startup - let Celery Beat handle it.
    This prevents import issues during startup.
    """
    logger.info(f"🚀 Starting {settings.PROJECT_NAME if hasattr(settings, 'PROJECT_NAME') else 'Polymarket Copy Trading API'}")
    logger.info(f"📊 Environment: {settings.ENVIRONMENT}")
    logger.info("✅ Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks - cleanup connections"""
    logger.info("Shutting down Polymarket Copy Trading API...")
    
    try:
        from app.api.deps import close_redis
        await close_redis()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")
    
    logger.info("✅ Shutdown complete")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Polymarket Copy Trading Platform API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
