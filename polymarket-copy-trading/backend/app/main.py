from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.api.websocket import websocket_endpoint
from app.core.config import settings

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

# WebSocket endpoint
app.add_websocket_route("/ws", websocket_endpoint)

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
