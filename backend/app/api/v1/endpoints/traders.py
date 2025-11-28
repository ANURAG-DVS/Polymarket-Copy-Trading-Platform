"""
Trader API Endpoints

Comprehensive endpoints for trader information, leaderboard, and performance data.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field
import hashlib
import json

from app.db.session import get_db
from app.models.api_key import Trade, User
from app.services.leaderboard import get_leaderboard_service, get_pnl_calculator
from app.services.cache.market_cache import get_market_cache_service


router = APIRouter(prefix="/traders", tags=["traders"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TraderStats(BaseModel):
    """Trader statistics"""
    wallet_address: str
    rank: Optional[int] = None
    
    # P&L
    pnl_7d: float
    pnl_30d: float
    pnl_total: float
    
    # Performance
    win_rate_7d: float
    win_rate_30d: float
    win_rate_total: float
    
    # Activity
    total_trades: int
    total_trades_7d: int
    total_trades_30d: int
    
    # Risk metrics
    sharpe_ratio: Optional[float] = None
    avg_trade_size: float = 0
    
    # Metadata
    last_trade_at: Optional[datetime] = None


class TraderProfile(BaseModel):
    """Complete trader profile"""
    wallet_address: str
    
    # Stats
    stats: TraderStats
    
    # Optional profile data
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Social
    followers: int = 0
    following: int = 0


class TradeResponse(BaseModel):
    """Single trade response"""
    id: int
    tx_hash: str
    market_id: str
    market_name: Optional[str] = None
    
    side: str  # BUY/SELL
    outcome: str  # YES/NO
    
    quantity: float
    entry_price: float
    entry_value_usd: float
    
    exit_price: Optional[float] = None
    exit_value_usd: Optional[float] = None
    
    realized_pnl_usd: Optional[float] = None
    realized_pnl_percent: Optional[float] = None
    
    status: str  # open/closed
    
    entry_timestamp: datetime
    exit_timestamp: Optional[datetime] = None


class PerformanceDataPoint(BaseModel):
    """Single data point for performance chart"""
    date: str  # ISO date
    pnl: float
    cumulative_pnl: float
    trades_count: int


class PerformanceChartData(BaseModel):
    """Performance chart data"""
    wallet_address: str
    timeframe: str
    data_points: List[PerformanceDataPoint]


# ============================================================================
# Helper Functions
# ============================================================================

def generate_etag(data: dict) -> str:
    """Generate ETag for response data"""
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(content.encode()).hexdigest()


def check_etag(request: Request, etag: str) -> bool:
    """Check if client's ETag matches current ETag"""
    client_etag = request.headers.get("If-None-Match")
    return client_etag == f'"{etag}"'


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/leaderboard", response_model=dict)
async def get_leaderboard(
    request: Request,
    timeframe: str = Query("7d", regex="^(7d|30d|all)$"),
    sort_by: str = Query("pnl", regex="^(pnl|winrate|volume|sharpe)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trader leaderboard with rankings.
    
    **Parameters:**
    - `timeframe`: 7d, 30d, or all (default: 7d)
    - `sort_by`: pnl, winrate, volume, sharpe (default: pnl)
    - `limit`: Max traders to return (1-500, default: 100)
    - `offset`: Pagination offset (default: 0)
    
    **Returns:**
    - Ranked list of traders with stats
    - Pagination metadata
    
    **Example:**
    ```
    GET /api/traders/leaderboard?timeframe=7d&limit=50
    ```
    """
    leaderboard = get_leaderboard_service()
    
    # Map timeframe to rank_by metric
    rank_by_map = {
        "7d": f"{sort_by}_7d" if sort_by in ["pnl", "winrate"] else "pnl_7d",
        "30d": f"{sort_by}_30d" if sort_by in ["pnl", "winrate"] else "pnl_30d",
        "all": f"{sort_by}_total" if sort_by in ["pnl", "winrate"] else "pnl_total"
    }
    
    rank_by = rank_by_map.get(timeframe, "pnl_7d")
    
    # Get traders (with extra for "has_more" check)
    traders = await leaderboard.get_top_traders(
        db,
        limit=limit + 1,
        rank_by=rank_by,
        use_cache=True
    )
    
    # Apply offset
    traders = traders[offset:]
    
    # Check if more results exist
    has_more = len(traders) > limit
    traders = traders[:limit]
    
    # Build response
    response_data = {
        "timeframe": timeframe,
        "sort_by": sort_by,
        "limit": limit,
        "offset": offset,
        "count": len(traders),
        "has_more": has_more,
        "traders": traders
    }
    
    # Generate ETag
    etag = generate_etag(response_data)
    
    # Check client ETag
    if check_etag(request, etag):
        return Response(status_code=304)  # Not Modified
    
    # Return with ETag header
    return JSONResponse(
        content=response_data,
        headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=60"}
    )


@router.get("/{wallet_address}", response_model=TraderProfile)
async def get_trader_profile(
    wallet_address: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete trader profile.
    
    **Parameters:**
    - `wallet_address`: Trader's wallet address
    
    **Returns:**
    - Complete trader profile with stats and metadata
    
    **Example:**
    ```
    GET /api/traders/0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1
    ```
    """
    pnl_calculator = get_pnl_calculator()
    leaderboard = get_leaderboard_service()
    
    # Get trader stats
    rolling_pnl = await pnl_calculator.calculate_rolling_pnl(db, wallet_address)
    sharpe = await pnl_calculator.calculate_sharpe_ratio(db, wallet_address)
    rank = await leaderboard.get_trader_rank(db, wallet_address)
    
    # Get last trade timestamp
    query = select(Trade.entry_timestamp).where(
        Trade.trader_wallet_address == wallet_address
    ).order_by(desc(Trade.entry_timestamp)).limit(1)
    
    result = await db.execute(query)
    last_trade = result.scalar()
    
    # Build stats
    stats = TraderStats(
        wallet_address=wallet_address,
        rank=rank,
        pnl_7d=float(rolling_pnl['pnl_7d']),
        pnl_30d=float(rolling_pnl['pnl_30d']),
        pnl_total=float(rolling_pnl['pnl_all_time']),
        win_rate_7d=rolling_pnl['win_rate_7d'],
        win_rate_30d=rolling_pnl['win_rate_30d'],
        win_rate_total=rolling_pnl['win_rate_all_time'],
        total_trades=rolling_pnl['total_trades_all_time'],
        total_trades_7d=rolling_pnl['total_trades_7d'],
        total_trades_30d=rolling_pnl['total_trades_30d'],
        sharpe_ratio=float(sharpe) if sharpe else None,
        last_trade_at=last_trade
    )
    
    # Build profile
    profile = TraderProfile(
        wallet_address=wallet_address,
        stats=stats,
        name=None,  # Would fetch from ENS or external service
        bio=None,
        avatar_url=None,
        followers=0,  # Would fetch from database
        following=0
    )
    
    # Generate ETag
    profile_dict = profile.dict()
    etag = generate_etag(profile_dict)
    
    # Check client ETag
    if check_etag(request, etag):
        return Response(status_code=304)
    
    # Return with caching headers
    return JSONResponse(
        content=profile_dict,
        headers={
            "ETag": f'"{etag}"',
            "Cache-Control": "public, max-age=60"
        }
    )


@router.get("/{wallet_address}/trades", response_model=dict)
async def get_trader_trades(
    wallet_address: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    market_id: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None, regex="^(YES|NO)$"),
    status: Optional[str] = Query(None, regex="^(open|closed)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trader's trade history.
    
    **Parameters:**
    - `wallet_address`: Trader address
    - `limit`: Max trades to return (default: 50)
    - `offset`: Pagination offset
    - `market_id`: Filter by market (optional)
    - `outcome`: Filter by YES/NO (optional)
    - `status`: Filter by open/closed (optional)
    - `start_date`: Filter by start date (optional)
    - `end_date`: Filter by end date (optional)
    
    **Returns:**
    - Paginated list of trades
    """
    # Build query
    query = select(Trade).where(Trade.trader_wallet_address == wallet_address)
    
    # Apply filters
    if market_id:
        query = query.where(Trade.market_id == market_id)
    
    if outcome:
        query = query.where(Trade.position == outcome)
    
    if status:
        query = query.where(Trade.status == status)
    
    if start_date:
        query = query.where(Trade.entry_timestamp >= start_date)
    
    if end_date:
        query = query.where(Trade.entry_timestamp <= end_date)
    
    # Count total
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and sorting
    query = query.order_by(desc(Trade.entry_timestamp))
    query = query.offset(offset).limit(limit + 1)
    
    # Execute
    result = await db.execute(query)
    trades = result.scalars().all()
    
    # Check has_more
    has_more = len(trades) > limit
    trades = trades[:limit]
    
    # Get market cache for names
    market_cache = get_market_cache_service()
    
    # Convert to response models
    trades_response = []
    for trade in trades:
        # Get market name from cache
        market_name = None
        market = await market_cache.get_market(trade.market_id)
        if market:
            market_name = market.name
        
        trade_response = TradeResponse(
            id=trade.id,
            tx_hash=trade.entry_tx_hash,
            market_id=trade.market_id,
            market_name=market_name,
            side="BUY" if trade.side == "buy" else "SELL",
            outcome=trade.position,
            quantity=float(trade.quantity),
            entry_price=float(trade.entry_price),
            entry_value_usd=float(trade.entry_value_usd),
            exit_price=float(trade.exit_price) if trade.exit_price else None,
            exit_value_usd=float(trade.exit_value_usd) if trade.exit_value_usd else None,
            realized_pnl_usd=float(trade.realized_pnl_usd) if trade.realized_pnl_usd else None,
            realized_pnl_percent=float(trade.realized_pnl_percent) if trade.realized_pnl_percent else None,
            status=trade.status,
            entry_timestamp=trade.entry_timestamp,
            exit_timestamp=trade.exit_timestamp
        )
        trades_response.append(trade_response.dict())
    
    return {
        "wallet_address": wallet_address,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "trades": trades_response
    }


@router.get("/{wallet_address}/performance", response_model=PerformanceChartData)
async def get_trader_performance(
    wallet_address: str,
    timeframe: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trader performance time-series data for charts.
    
    **Parameters:**
    - `wallet_address`: Trader address
    - `timeframe`: 7d, 30d, 90d, or all (default: 30d)
    
    **Returns:**
    - Daily P&L data points for charting
    
    **Format:**
    Optimized for Chart.js and Recharts libraries.
    
    **Example Response:**
    ```json
    {
      "wallet_address": "0x123...",
      "timeframe": "30d",
      "data_points": [
        {
          "date": "2024-01-01",
          "pnl": 125.50,
          "cumulative_pnl": 1250.00,
          "trades_count": 5
        }
      ]
    }
    ```
    """
    # Calculate days
    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    days = days_map.get(timeframe)
    
    # Get trades
    query = select(Trade).where(Trade.trader_wallet_address == wallet_address)
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.where(Trade.entry_timestamp >= cutoff)
    
    query = query.order_by(Trade.entry_timestamp)
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    # Group by date and calculate P&L
    from collections import defaultdict
    daily_data = defaultdict(lambda: {"pnl": 0, "trades": 0})
    
    for trade in trades:
        if trade.exit_timestamp and trade.realized_pnl_usd:
            date_key = trade.exit_timestamp.date().isoformat()
            daily_data[date_key]["pnl"] += float(trade.realized_pnl_usd)
            daily_data[date_key]["trades"] += 1
    
    # Build data points with cumulative P&L
    data_points = []
    cumulative_pnl = 0
    
    for date in sorted(daily_data.keys()):
        pnl = daily_data[date]["pnl"]
        cumulative_pnl += pnl
        
        data_points.append(PerformanceDataPoint(
            date=date,
            pnl=round(pnl, 2),
            cumulative_pnl=round(cumulative_pnl, 2),
            trades_count=daily_data[date]["trades"]
        ))
    
    return PerformanceChartData(
        wallet_address=wallet_address,
        timeframe=timeframe,
        data_points=data_points
    )
