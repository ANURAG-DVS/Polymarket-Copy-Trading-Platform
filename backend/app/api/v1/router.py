"""
API Version 1 Router

Consolidates all V1 API endpoints.
"""

from fastapi import APIRouter

# Import endpoints
from app.api.v1.endpoints import (
    leaderboard, markets, traders, trader_discovery, 
    auth, user, subscription, dashboard, admin, emergency
)

router = APIRouter()

# Include routers
router.include_router(auth.router)
router.include_router(user.router)
router.include_router(subscription.router)
router.include_router(dashboard.router)
router.include_router(admin.router)
router.include_router(emergency.router)
router.include_router(leaderboard.router)
router.include_router(markets.router)
router.include_router(traders.router)
router.include_router(trader_discovery.router)

@router.get("/")
async def api_root():
    """API root endpoint"""
    return {"message": "Polymarket Copy Trading API v1"}
