"""
Trader API endpoints for leaderboard, statistics, and trader details.

Provides REST API endpoints for:
- Trader leaderboard with filtering and pagination
- Individual trader details and performance
- Time-series statistics for charts
- Position/trade history
- Trader search

All endpoints include Redis caching for performance and proper error handling.
"""

from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import redis.asyncio as aioredis
import logging

from app.api.deps import get_db, get_redis, get_cache_key, get_cached_data, set_cached_data
from app.schemas.trader_v2 import (
    TraderV2Response,
    TraderV2LeaderboardResponse,
    TraderV2ListResponse,
    TraderStatsResponse,
    TraderMarketResponse
)
from app.models.trader_v2 import TraderV2, TraderStats, TraderMarket, PositionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traders", tags=["traders"])


# ============================================================================
# Leaderboard Endpoint
# ============================================================================

@router.get(
    "/leaderboard",
    response_model=TraderV2ListResponse,
    summary="Get Trader Leaderboard",
    description="""
    Get top traders ranked by performance with filtering and pagination.
    
    Results are cached in Redis for 1 minute for fast response times.
    
    **Filtering Options:**
    - timeframe: Activity window (7d, 30d, all)
    - min_trades: Minimum number of trades
    - min_winrate: Minimum win rate percentage
    - limit: Results per page
    - offset: Pagination offset
    """
)
async def get_leaderboard(
    timeframe: str = Query("7d", regex="^(7d|30d|all)$", description="Time window for ranking"),
    limit: int = Query(100, ge=1, le=500, description="Number of traders to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    min_trades: int = Query(10, ge=1, description="Minimum trades filter"),
    min_winrate: float = Query(0, ge=0, le=100, description="Minimum win rate filter"),
    db: AsyncSession = Depends(get_db),
    cache: aioredis.Redis = Depends(get_redis)
) -> TraderV2ListResponse:
    """
    Get trader leaderboard with caching and filtering.
    
    Caching Strategy:
    1. Check Redis cache first
    2. If miss, query database
    3. Cache result for 60 seconds
    4. Return data with pagination metadata
    """
    # Generate cache key
    cache_key = get_cache_key(
        "leaderboard",
        timeframe=timeframe,
        limit=limit,
        offset=offset,
        min_trades=min_trades,
        min_winrate=min_winrate
    )
    
    # Try cache first
    cached = await get_cached_data(cache, cache_key)
    if cached:
        logger.debug(f"Cache hit for leaderboard: {cache_key}")
        return TraderV2ListResponse(**cached)
    
    try:
        # Build base query
        query = select(TraderV2).where(
            and_(
                TraderV2.total_trades >= min_trades,
                TraderV2.win_rate >= min_winrate
            )
        ).order_by(desc(TraderV2.total_pnl))
        
        # Execute count query
        count_query = select(func.count()).select_from(TraderV2).where(
            and_(
                TraderV2.total_trades >= min_trades,
                TraderV2.win_rate >= min_winrate
            )
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await db.execute(query)
        traders = result.scalars().all()
        
        # Add ranks
        traders_with_ranks = []
        for idx, trader in enumerate(traders):
            trader_dict = {
                "rank": offset + idx + 1,
                "wallet_address": trader.wallet_address,
                "username": trader.username,
                "total_volume": float(trader.total_volume) if trader.total_volume else 0.0,
                "total_pnl": float(trader.total_pnl) if trader.total_pnl else 0.0,
                "win_rate": float(trader.win_rate) if trader.win_rate else 0.0,
                "total_trades": trader.total_trades,
                "markets_traded": trader.markets_traded,
                "last_trade_at": trader.last_trade_at.isoformat() if trader.last_trade_at else None,
                "created_at": trader.created_at.isoformat() if trader.created_at else None,
                "updated_at": trader.updated_at.isoformat() if trader.updated_at else None,
            }
            traders_with_ranks.append(trader_dict)
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        current_page = (offset // limit) + 1
        
        # Build response
        response_data = {
            "traders": traders_with_ranks,
            "total": total,
            "page": current_page,
            "limit": limit,
            "total_pages": total_pages
        }
        
        # Cache the result
        await set_cached_data(cache, cache_key, response_data, ttl=60)
        
        logger.info(f"Leaderboard query: {len(traders)} traders, total={total}")
        
        return TraderV2ListResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")


# ============================================================================
# Trader Details Endpoint
# ============================================================================

@router.get(
    "/{wallet_address}",
    response_model=Dict[str, Any],
    summary="Get Trader Details",
    description="""
    Get comprehensive information about a specific trader.
    
    **Returns:**
    - Basic trader info (address, stats, timestamps)
    - Recent positions (last 20)
    - Performance chart data (30 days of daily stats)
    - All-time, 7-day, and 30-day metrics
    """
)
async def get_trader_details(
    wallet_address: str = Path(..., regex="^0x[a-fA-F0-9]{40}$", description="Ethereum wallet address"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed information about a specific trader."""
    
    try:
        # Fetch trader
        trader = await db.get(TraderV2, wallet_address)
        
        if not trader:
            raise HTTPException(
                status_code=404,
                detail=f"Trader not found: {wallet_address}"
            )
        
        # Fetch recent positions (last 20)
        positions_query = select(TraderMarket).where(
            TraderMarket.wallet_address == wallet_address
        ).order_by(desc(TraderMarket.created_at)).limit(20)
        
        positions_result = await db.execute(positions_query)
        positions = positions_result.scalars().all()
        
        # Fetch 30-day stats for chart
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        stats_query = select(TraderStats).where(
            and_(
                TraderStats.wallet_address == wallet_address,
                TraderStats.date >= thirty_days_ago.date()
            )
        ).order_by(TraderStats.date)
        
        stats_result = await db.execute(stats_query)
        daily_stats = stats_result.scalars().all()
        
        # Calculate 7-day and 30-day metrics
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        pnl_7d_query = select(func.sum(TraderStats.daily_pnl)).where(
            and_(
                TraderStats.wallet_address == wallet_address,
                TraderStats.date >= seven_days_ago.date()
            )
        )
        pnl_7d_result = await db.execute(pnl_7d_query)
        pnl_7d = pnl_7d_result.scalar() or 0
        
        pnl_30d_query = select(func.sum(TraderStats.daily_pnl)).where(
            and_(
                TraderStats.wallet_address == wallet_address,
                TraderStats.date >= thirty_days_ago.date()
            )
        )
        pnl_30d_result = await db.execute(pnl_30d_query)
        pnl_30d = pnl_30d_result.scalar() or 0
        
        # Build response
        response = {
            "trader": trader.to_dict(),
            "metrics": {
                "pnl_7d": float(pnl_7d),
                "pnl_30d": float(pnl_30d),
                "all_time_pnl": float(trader.total_pnl) if trader.total_pnl else 0.0,
            },
            "recent_positions": [pos.to_dict() for pos in positions],
            "chart_data": [
                {
                    "date": stat.date.isoformat(),
                    "pnl": float(stat.daily_pnl) if stat.daily_pnl else 0.0,
                    "volume": float(stat.daily_volume) if stat.daily_volume else 0.0,
                    "trades": stat.trades_count
                }
                for stat in daily_stats
            ]
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching trader details for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch trader details")


# ============================================================================
# Trader Statistics Endpoint
# ============================================================================

@router.get(
    "/{wallet_address}/statistics",
    summary="Get Trader Statistics",
    description="""
    Get time-series statistics for a trader.
    
    Returns daily P&L, volume, and trade counts for chart visualization.
    If no date range specified, returns last 30 days.
    """
)
async def get_trader_statistics(
    wallet_address: str = Path(..., regex="^0x[a-fA-F0-9]{40}$"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get time-series statistics for charts."""
    
    try:
        # Verify trader exists
        trader = await db.get(TraderV2, wallet_address)
        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")
        
        # Set default date range (last 30 days)
        if not end_date:
            end_date = datetime.utcnow().date()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Validate date range
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
        
        # Fetch stats
        query = select(TraderStats).where(
            and_(
                TraderStats.wallet_address == wallet_address,
                TraderStats.date >= start_date,
                TraderStats.date <= end_date
            )
        ).order_by(TraderStats.date)
        
        result = await db.execute(query)
        stats = result.scalars().all()
        
        # Calculate summary
        total_pnl = sum(float(s.daily_pnl) if s.daily_pnl else 0.0 for s in stats)
        avg_volume = sum(float(s.daily_volume) if s.daily_volume else 0.0 for s in stats) / len(stats) if stats else 0
        
        best_day = max(stats, key=lambda s: s.daily_pnl) if stats else None
        
        # Build response
        response = {
            "wallet_address": wallet_address,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "data": [
                {
                    "date": s.date.isoformat(),
                    "pnl": float(s.daily_pnl) if s.daily_pnl else 0.0,
                    "volume": float(s.daily_volume) if s.daily_volume else 0.0,
                    "trades": s.trades_count,
                    "wins": s.win_count,
                    "losses": s.loss_count
                }
                for s in stats
            ],
            "summary": {
                "total_pnl": total_pnl,
                "avg_daily_volume": avg_volume,
                "days_count": len(stats),
                "best_day": {
                    "date": best_day.date.isoformat(),
                    "pnl": float(best_day.daily_pnl) if best_day.daily_pnl else 0.0
                } if best_day else None
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching statistics for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")


# ============================================================================
# Trader Positions Endpoint
# ============================================================================

@router.get(
    "/{wallet_address}/positions",
    summary="Get Trader Positions",
    description="""
    Get trader's positions/trades with filtering.
    
    **Filters:**
    - status: Filter by OPEN or CLOSED positions
    - limit/offset: Pagination
    """
)
async def get_trader_positions(
    wallet_address: str = Path(..., regex="^0x[a-fA-F0-9]{40}$"),
    status: Optional[str] = Query(None, regex="^(open|closed)$", description="Filter by position status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get trader positions with filtering."""
    
    try:
        # Verify trader exists
        trader = await db.get(TraderV2, wallet_address)
        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")
        
        # Build query
        query = select(TraderMarket).where(TraderMarket.wallet_address == wallet_address)
        
        # Apply status filter
        if status:
            pos_status = PositionStatus.OPEN if status.lower() == "open" else PositionStatus.CLOSED
            query = query.where(TraderMarket.status == pos_status)
        
        # Count total
        count_query = select(func.count()).select_from(TraderMarket).where(TraderMarket.wallet_address == wallet_address)
        if status:
            count_query = count_query.where(TraderMarket.status == pos_status)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination and sorting
        query = query.order_by(desc(TraderMarket.created_at)).limit(limit).offset(offset)
        
        # Execute
        result = await db.execute(query)
        positions = result.scalars().all()
        
        # Build response
        response = {
            "wallet_address": wallet_address,
            "positions": [p.to_dict() for p in positions],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching positions for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch positions")


# ============================================================================
# Search Traders Endpoint
# ============================================================================

@router.get(
    "/search",
    summary="Search Traders",
    description="""
    Search traders by wallet address (partial match).
    
    Returns top 20 matches ordered by total P&L.
    """
)
async def search_traders(
    q: str = Query(..., min_length=3, description="Search query (minimum 3 characters)"),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Search traders by wallet address."""
    
    try:
        # Build query with ILIKE for partial match
        query = select(TraderV2).where(
            TraderV2.wallet_address.ilike(f"%{q}%")
        ).order_by(desc(TraderV2.total_pnl)).limit(20)
        
        result = await db.execute(query)
        traders = result.scalars().all()
        
        # Build response
        results = [
            {
                "wallet_address": t.wallet_address,
                "username": t.username,
                "total_pnl": float(t.total_pnl) if t.total_pnl else 0.0,
                "win_rate": float(t.win_rate) if t.win_rate else 0.0,
                "total_trades": t.total_trades
            }
            for t in traders
        ]
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching traders with query '{q}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")
