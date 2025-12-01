"""
Trader API endpoints with explicit loading control.

CRITICAL FIX: Uses manual serialization via to_dict() to avoid ORM relationship loading.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.trader_v2 import TraderV2, TraderStats, TraderMarket
from app.schemas.trader_v2 import (
    TraderV2LeaderboardResponse,
    TraderV2DetailResponse,
    TraderV2Response,
    TraderStatsResponse,
    TraderMarketResponse,
)

router = APIRouter()


@router.get("/leaderboard", response_model=List[TraderV2LeaderboardResponse])
async def get_leaderboard(
    timeframe: str = Query("7d", pattern="^(7d|30d|all)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_trades: int = Query(10, ge=1),
    min_winrate: float = Query(0, ge=0, le=100),
    db: Session = Depends(get_db),
) -> List[TraderV2LeaderboardResponse]:
    """
    Get top traders leaderboard.
    FIXED: No relationship loading, manual serialization.
    """
    try:
        # Query WITHOUT loading relationships
        query = db.query(TraderV2).filter(
            and_(
                TraderV2.total_trades >= min_trades,
                TraderV2.win_rate >= min_winrate
            )
        )
        
        # Order by P&L descending
        query = query.order_by(desc(TraderV2.total_pnl))
        
        # Apply pagination
        traders = query.offset(offset).limit(limit).all()
        
        # Manually construct response to avoid relationship loading
        response = []
        for rank, trader in enumerate(traders, start=offset + 1):
            # Use to_dict() method to avoid ORM relationships
            trader_dict = trader.to_dict(include_relations=False)
            trader_dict["rank"] = rank
            trader_dict["pnl_7d"] = None  # TODO: Calculate from stats
            trader_dict["pnl_30d"] = None  # TODO: Calculate from stats
            trader_dict["win_rate_7d"] = None  # TODO: Calculate from stats
            response.append(TraderV2LeaderboardResponse(**trader_dict))
        
        return response
    
    except Exception as e:
        print(f"Error in get_leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}", response_model=TraderV2DetailResponse)
async def get_trader_details(
    wallet_address: str = Path(..., pattern="^0x[a-fA-F0-9]{40}$"),
    db: Session = Depends(get_db),
) -> TraderV2DetailResponse:
    """
    Get detailed trader information.
    FIXED: Explicit loading control.
    """
    try:
        # Query trader WITHOUT auto-loading relationships
        trader = db.query(TraderV2).filter(
            TraderV2.wallet_address == wallet_address.lower()
        ).first()
        
        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")
        
        # Get base trader data
        trader_dict = trader.to_dict(include_relations=False)
        
        # Manually count stats and markets (separate queries)
        stats_count = db.query(TraderStats).filter(
            TraderStats.wallet_address == wallet_address.lower()
        ).count()
        
        markets_count = db.query(TraderMarket).filter(
            TraderMarket.wallet_address == wallet_address.lower()
        ).count()
        
        # Add counts to response
        trader_dict["stats_count"] = stats_count
        trader_dict["markets_count"] = markets_count
        
        # Optionally load recent stats (last 30 days)
        recent_stats = db.query(TraderStats).filter(
            and_(
                TraderStats.wallet_address == wallet_address.lower(),
                TraderStats.date >= datetime.utcnow().date() - timedelta(days=30)
            )
        ).order_by(desc(TraderStats.date)).limit(30).all()
        
        trader_dict["recent_stats"] = [
            TraderStatsResponse(**stat.to_dict()) for stat in recent_stats
        ]
        
        # Optionally load recent markets
        recent_markets = db.query(TraderMarket).filter(
            TraderMarket.wallet_address == wallet_address.lower()
        ).order_by(desc(TraderMarket.created_at)).limit(10).all()
        
        trader_dict["recent_markets"] = [
            TraderMarketResponse(**market.to_dict()) for market in recent_markets
        ]
        
        return TraderV2DetailResponse(**trader_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_trader_details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}/statistics", response_model=List[TraderStatsResponse])
async def get_trader_statistics(
    wallet_address: str = Path(..., pattern="^0x[a-fA-F0-9]{40}$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> List[TraderStatsResponse]:
    """
    Get time-series statistics for a trader.
    FIXED: No relationship loading.
    """
    try:
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Query stats WITHOUT loading trader relationship
        stats = db.query(TraderStats).filter(
            and_(
                TraderStats.wallet_address == wallet_address.lower(),
                TraderStats.date >= start_date.date(),
                TraderStats.date <= end_date.date()
            )
        ).order_by(TraderStats.date).all()
        
        # Manually serialize
        return [TraderStatsResponse(**stat.to_dict()) for stat in stats]
    
    except Exception as e:
        print(f"Error in get_trader_statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=List[TraderV2Response])
async def search_traders(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[TraderV2Response]:
    """
    Search traders by wallet address or username.
    FIXED: No relationship loading.
    """
    try:
        search_term = query.lower()
        
        # Query WITHOUT loading relationships
        traders = db.query(TraderV2).filter(
            (TraderV2.wallet_address.like(f"%{search_term}%")) |
            (TraderV2.username.like(f"%{search_term}%"))
        ).limit(limit).all()
        
        # Manually serialize
        return [TraderV2Response(**trader.to_dict(include_relations=False)) for trader in traders]
    
    except Exception as e:
        print(f"Error in search_traders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
