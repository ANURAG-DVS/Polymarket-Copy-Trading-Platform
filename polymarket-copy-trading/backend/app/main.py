from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.api.websocket import websocket_endpoint
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Polymarket Copy Trading API",
    description="Backend API for Polymarket copy trading platform",
    version="1.0.0"
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

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Include admin router
from app.api.v1.endpoints import admin
app.include_router(admin.router, prefix="/api/v1")

# WebSocket endpoint
app.add_websocket_route("/ws", websocket_endpoint)


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    
    Initializes:
    - Trader data fetching (triggered once on startup)
    - Cache warming
    - Background task scheduling
    """
    logger.info("Starting Polymarket Copy Trading API...")
    
    try:
        # Trigger initial trader data fetch
        from app.workers.trader_tasks import fetch_top_traders_task
        
        logger.info("Queuing initial trader data fetch...")
        fetch_top_traders_task.delay(limit=100, timeframe_days=7)
        
        logger.info("Startup tasks queued successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        # Don't fail startup, just log the error


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    
    Cleanup:
    - Close Redis connections
    - Close database connections
    """
    logger.info("Shutting down Polymarket Copy Trading API...")
    
    try:
        # Close Redis connection
        from app.api.deps import close_redis
        await close_redis()
        
        logger.info("Shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Polymarket Copy Trading API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "polymarket-copy-trading"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
