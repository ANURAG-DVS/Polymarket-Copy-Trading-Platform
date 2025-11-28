"""
Leaderboard API Endpoints

FastAPI endpoints for accessing trader leaderboard.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.leaderboard import get_leaderboard_service, get_pnl_calculator


router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/top")
async def get_top_traders(
    limit: int = Query(100, ge=1, le=500),
    rank_by: str = Query("pnl_7d", regex="^(pnl_7d|pnl_30d|pnl_total|win_rate_7d|sharpe)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get top traders on leaderboard.
    
    **Parameters:**
    - `limit`: Number of traders to return (1-500, default: 100)
    - `rank_by`: Metric to rank by (pnl_7d, pnl_30d, pnl_total, win_rate_7d, sharpe)
    
    **Returns:**
    - List of ranked traders with stats
    """
    leaderboard = get_leaderboard_service()
    
    traders = await leaderboard.get_top_traders(
        db,
        limit=limit,
        rank_by=rank_by
    )
    
    return {
        "count": len(traders),
        "rank_by": rank_by,
        "traders": traders
    }


@router.get("/trader/{wallet_address}")
async def get_trader_stats(
    wallet_address: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive stats for a specific trader.
    
    **Parameters:**
    - `wallet_address`: Trader's wallet address
    
    **Returns:**
    - Trader stats including P&L, win rate, rank
    """
    pnl_calculator = get_pnl_calculator()
    leaderboard = get_leaderboard_service()
    
    # Get rolling P&L
    stats = await pnl_calculator.calculate_rolling_pnl(db, wallet_address)
    
    # Get rank
    rank = await leaderboard.get_trader_rank(db, wallet_address)
    
    return {
        "wallet_address": wallet_address,
        "rank": rank,
        "pnl_7d": float(stats['pnl_7d']),
        "pnl_30d": float(stats['pnl_30d']),
        "pnl_all_time": float(stats['pnl_all_time']),
        "win_rate_7d": stats['win_rate_7d'],
        "win_rate_30d": stats['win_rate_30d'],
        "win_rate_all_time": stats['win_rate_all_time'],
        "total_trades_7d": stats['total_trades_7d'],
        "total_trades_30d": stats['total_trades_30d'],
        "total_trades_all_time": stats['total_trades_all_time']
    }


@router.get("/trending")
async def get_trending_traders(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trending traders (biggest 7-day gains).
    
    **Parameters:**
    - `limit`: Number of traders (default: 10)
    
    **Returns:**
    - List of trending traders
    """
    leaderboard = get_leaderboard_service()
    
    traders = await leaderboard.get_trending_traders(db, limit=limit)
    
    return {
        "count": len(traders),
        "traders": traders
    }
