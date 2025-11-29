from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.api.deps import get_db
from app.schemas.trader import (
    TraderResponse,
    TraderListResponse,
    TradeResponse,
    TraderFilters
)
from app.services.trader_service import TraderService
import math

router = APIRouter()

@router.get("/leaderboard", response_model=TraderListResponse)
async def get_traders_leaderboard(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    timeframe: str = Query("7d", regex="^(7d|30d|all)$"),
    min_pnl: Optional[float] = None,
    min_win_rate: Optional[float] = None,
    min_trades: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = Query("rank", regex="^(rank|pnl_7d|pnl_30d|win_rate|total_trades)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get traders leaderboard with filters and pagination
    
    - **timeframe**: 7d, 30d, or all
    - **min_pnl**: Minimum P&L filter
    - **min_win_rate**: Minimum win rate (percentage)
    - **min_trades**: Minimum number of trades
    - **search**: Search by wallet address
    - **sort_by**: Column to sort by
    - **sort_order**: asc or desc
    """
    trader_service = TraderService(db)
    
    filters = TraderFilters(
        timeframe=timeframe,
        min_pnl=min_pnl,
        min_win_rate=min_win_rate,
        min_trades=min_trades,
        search=search,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    traders, total = await trader_service.get_leaderboard(filters)
    
    total_pages = math.ceil(total / limit)
    
    return TraderListResponse(
        traders=[TraderResponse.from_orm(t) for t in traders],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

@router.get("/{trader_id}", response_model=TraderResponse)
async def get_trader_details(
    trader_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific trader"""
    trader_service = TraderService(db)
    
    trader = await trader_service.get_trader_by_id(trader_id)
    
    if not trader:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trader not found"
        )
    
    return TraderResponse.from_orm(trader)

@router.get("/{trader_id}/trades")
async def get_trader_trades(
    trader_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get recent trades for a trader"""
    trader_service = TraderService(db)
    
    trades = await trader_service.get_trader_trades(trader_id, limit, offset)
    
    return {
        "trades": [TradeResponse.from_orm(t) for t in trades],
        "count": len(trades)
    }

@router.get("/{trader_id}/pnl-history")
async def get_trader_pnl_history(
    trader_id: int,
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get trader's P&L history over time"""
    trader_service = TraderService(db)
    
    history = await trader_service.get_trader_pnl_history(trader_id, days)
    
    return {
        "history": history,
        "trader_id": trader_id,
        "days": days
    }
