from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.positions import (
    PositionFilters,
    OpenPositionResponse,
    ClosedPositionResponse,
    ClosePositionRequest
)
from app.services.positions_service import PositionsService
import math

router = APIRouter()

@router.get("/open")
async def get_open_positions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    trader_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's open positions with filters"""
    
    positions_service = PositionsService(db)
    
    filters = PositionFilters(
        trader_id=trader_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit
    )
    
    positions, total = await positions_service.get_open_positions(
        user_id=current_user.id,
        filters=filters
    )
    
    return {
        "positions": [OpenPositionResponse.from_orm(p) for p in positions],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit)
    }

@router.get("/closed")
async def get_closed_positions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    trader_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's closed positions with filters"""
    
    positions_service = PositionsService(db)
    
    filters = PositionFilters(
        trader_id=trader_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit
    )
    
    positions, total = await positions_service.get_closed_positions(
        user_id=current_user.id,
        filters=filters
    )
    
    # Calculate duration for each position
    response_positions = []
    for p in positions:
        duration_hours = 0
        if p.closed_at and p.created_at:
            duration_hours = (p.closed_at - p.created_at).total_seconds() / 3600
        
        response_positions.append({
            **ClosedPositionResponse.from_orm(p).dict(),
            "duration_hours": duration_hours
        })
    
    return {
        "positions": response_positions,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit)
    }

@router.post("/close")
async def close_position(
    request: ClosePositionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually close an open position"""
    
    positions_service = PositionsService(db)
    
    position = await positions_service.close_position(
        position_id=request.position_id,
        user_id=current_user.id
    )
    
    return {
        "message": "Position closed successfully",
        "position": OpenPositionResponse.from_orm(position)
    }

@router.get("/{position_id}/details")
async def get_position_details(
    position_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed position information with timeline"""
    
    positions_service = PositionsService(db)
    
    details = await positions_service.get_position_details(
        position_id=position_id,
        user_id=current_user.id
    )
    
    return details

@router.get("/export/csv")
async def export_positions_csv(
    status: str = Query("closed", regex="^(open|closed)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export positions to CSV"""
    
    # TODO: Implement CSV export
    # For now, return a placeholder
    return {
        "message": "CSV export not yet implemented",
        "status": status
    }
