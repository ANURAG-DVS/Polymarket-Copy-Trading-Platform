from fastapi import APIRouter
from app.api.v1.endpoints import auth, traders, copy_relationships, dashboard, positions, settings

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(traders.router, prefix="/traders", tags=["traders"])
api_router.include_router(copy_relationships.router, prefix="/copy-relationships", tags=["copy-relationships"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
