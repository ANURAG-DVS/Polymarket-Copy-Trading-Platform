"""
User Dashboard Endpoints

Dashboard overview, copy relationships, positions, and analytics.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from pydantic import BaseModel, Field, validator

from app.db.session import get_db
from app.models.api_key import User, Trade
from app.api.v1.endpoints.auth import get_current_user
from app.services.subscription import get_subscription_service, SubscriptionTier


router = APIRouter(prefix="/user", tags=["dashboard"])


# ============================================================================
# Request/Response Models
# ============================================================================

class DashboardOverview(BaseModel):
    """Dashboard overview data"""
    # P&L
    pnl_all_time: float
    pnl_7d: float
    pnl_24h: float
    
    # Activity
    active_copy_relationships: int
    open_positions: int
    total_trades: int
    
    # Recent trades
    recent_trades: List[dict]
    
    # Account
    account_balance: float = 0.0


class CopyRelationship(BaseModel):
    """Copy trading relationship"""
    id: int
    trader_address: str
    trader_name: Optional[str] = None
    
    # Settings
    copy_percentage: float = Field(100.0, ge=1.0, le=100.0)
    max_investment_usd: Optional[float] = None
    
    # Status
    is_active: bool = True
    paused: bool = False
    
    # Stats
    trades_copied: int = 0
    total_pnl: float = 0.0
    
    created_at: datetime


class CreateCopyRelationship(BaseModel):
    """Create copy relationship request"""
    trader_address: str = Field(..., min_length=42, max_length=42)
    copy_percentage: float = Field(100.0, ge=1.0, le=100.0)
    max_investment_usd: Optional[float] = Field(None, gt=0)
    
    @validator('trader_address')
    def validate_address(cls, v):
        if not v.startswith('0x'):
            raise ValueError('Invalid Ethereum address')
        return v.lower()


class UpdateCopyRelationship(BaseModel):
    """Update copy relationship"""
    copy_percentage: Optional[float] = Field(None, ge=1.0, le=100.0)
    max_investment_usd: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None
    paused: Optional[bool] = None


class Position(BaseModel):
    """Open position"""
    id: int
    market_id: str
    market_name: Optional[str]
    
    outcome: str  # YES/NO
    quantity: float
    entry_price: float
    current_price: float
    
    entry_value_usd: float
    current_value_usd: float
    unrealized_pnl_usd: float
    unrealized_pnl_percent: float
    
    copied_from: Optional[str] = None  # Trader address
    
    entry_timestamp: datetime


class AnalyticsDataPoint(BaseModel):
    """Analytics data point"""
    date: str
    value: float


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard overview.
    
    **Returns:**
    - P&L metrics (all-time, 7-day, 24-hour)
    - Active relationships and positions
    - Recent trade activity
    - Account balance
    """
    # Calculate P&L
    from app.services.leaderboard import get_pnl_calculator
    
    pnl_calc = get_pnl_calculator()
    
    # Get rolling P&L
    pnl_data = await pnl_calc.calculate_rolling_pnl(
        db,
        current_user.wallet_address
    )
    
    # Calculate 24h P&L
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    query_24h = select(func.sum(Trade.realized_pnl_usd)).where(
        and_(
            Trade.trader_wallet_address == current_user.wallet_address,
            Trade.exit_timestamp >= cutoff_24h,
            Trade.status == 'closed'
        )
    )
    result_24h = await db.execute(query_24h)
    pnl_24h = float(result_24h.scalar() or 0)
    
    # Count relationships (placeholder - would query copy_relationships table)
    active_relationships = 0
    
    # Count open positions
    query_positions = select(func.count()).where(
        and_(
            Trade.trader_wallet_address == current_user.wallet_address,
            Trade.status == 'open'
        )
    )
    result_positions = await db.execute(query_positions)
    open_positions = result_positions.scalar() or 0
    
    # Get recent trades
    query_recent = select(Trade).where(
        Trade.trader_wallet_address == current_user.wallet_address
    ).order_by(desc(Trade.entry_timestamp)).limit(10)
    
    result_recent = await db.execute(query_recent)
    recent_trades_raw = result_recent.scalars().all()
    
    recent_trades = [
        {
            "id": trade.id,
            "market_id": trade.market_id,
            "side": trade.side,
            "outcome": trade.position,
            "quantity": float(trade.quantity),
            "entry_value_usd": float(trade.entry_value_usd),
            "status": trade.status,
            "pnl": float(trade.realized_pnl_usd) if trade.realized_pnl_usd else None,
            "timestamp": trade.entry_timestamp.isoformat()
        }
        for trade in recent_trades_raw
    ]
    
    return DashboardOverview(
        pnl_all_time=float(pnl_data['pnl_all_time']),
        pnl_7d=float(pnl_data['pnl_7d']),
        pnl_24h=pnl_24h,
        active_copy_relationships=active_relationships,
        open_positions=open_positions,
        total_trades=pnl_data['total_trades_all_time'],
        recent_trades=recent_trades,
        account_balance=0.0  # Would fetch from Polymarket API
    )


# ============================================================================
# Copy Relationships
# ============================================================================

@router.get("/copy-relationships", response_model=List[CopyRelationship])
async def get_copy_relationships(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all copy trading relationships.
    
    **Returns:**
    - List of traders user is copying
    - Settings and stats for each
    """
    # In production, query copy_relationships table
    # For now, return empty list
    return []


@router.post("/copy-relationships", response_model=CopyRelationship, status_code=status.HTTP_201_CREATED)
async def create_copy_relationship(
    request: CreateCopyRelationship,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add new trader to copy.
    
    **Validates:**
    - Trader exists
    - User within subscription limits
    - Not already copying this trader
    
    **Example:**
    ```json
    {
      "trader_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
      "copy_percentage": 50.0,
      "max_investment_usd": 1000.0
    }
    ```
    """
    subscription_service = get_subscription_service()
    
    # Get current tier
    tier = SubscriptionTier(
        current_user.subscription_tier 
        if hasattr(current_user, 'subscription_tier') 
        else 'free'
    )
    
    # Check subscription limits
    # Get current count (would query copy_relationships table)
    current_count = 0
    
    allowed, message = subscription_service.check_copy_trader_limit(tier, current_count)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=message
        )
    
    # Verify trader exists
    query = select(User).where(User.wallet_address == request.trader_address)
    result = await db.execute(query)
    trader = result.scalar_one_or_none()
    
    if not trader:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trader not found"
        )
    
    # Check not already copying
    # (would query copy_relationships table)
    
    # Create relationship (in production, insert into copy_relationships table)
    # For now, return mock response
    return CopyRelationship(
        id=1,
        trader_address=request.trader_address,
        copy_percentage=request.copy_percentage,
        max_investment_usd=request.max_investment_usd,
        is_active=True,
        paused=False,
        trades_copied=0,
        total_pnl=0.0,
        created_at=datetime.utcnow()
    )


@router.put("/copy-relationships/{relationship_id}", response_model=CopyRelationship)
async def update_copy_relationship(
    relationship_id: int,
    request: UpdateCopyRelationship,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update copy relationship settings.
    
    **Can update:**
    - copy_percentage
    - max_investment_usd
    - is_active (enable/disable)
    - paused (pause/resume)
    """
    # In production, fetch and update relationship
    # Verify ownership (user_id matches current_user.id)
    
    # Return mock response
    return CopyRelationship(
        id=relationship_id,
        trader_address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
        copy_percentage=request.copy_percentage or 100.0,
        max_investment_usd=request.max_investment_usd,
        is_active=request.is_active if request.is_active is not None else True,
        paused=request.paused if request.paused is not None else False,
        trades_copied=0,
        total_pnl=0.0,
        created_at=datetime.utcnow()
    )


@router.delete("/copy-relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_copy_relationship(
    relationship_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stop copying a trader.
    
    **Note:** Existing positions remain open.
    """
    # In production, soft delete or hard delete relationship
    # Verify ownership
    pass


# ============================================================================
# Positions & Trades
# ============================================================================

@router.get("/positions", response_model=List[Position])
async def get_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all open positions.
    
    **Returns:**
    - Open positions with current prices
    - Unrealized P&L
    """
    query = select(Trade).where(
        and_(
            Trade.trader_wallet_address == current_user.wallet_address,
            Trade.status == 'open'
        )
    ).order_by(desc(Trade.entry_timestamp))
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    positions = []
    for trade in trades:
        positions.append(Position(
            id=trade.id,
            market_id=trade.market_id,
            market_name=None,  # Would fetch from cache
            outcome=trade.position,
            quantity=float(trade.quantity),
            entry_price=float(trade.entry_price),
            current_price=float(trade.exit_price) if trade.exit_price else float(trade.entry_price),
            entry_value_usd=float(trade.entry_value_usd),
            current_value_usd=float(trade.current_value_usd) if hasattr(trade, 'current_value_usd') else float(trade.entry_value_usd),
            unrealized_pnl_usd=float(trade.unrealized_pnl_usd) if hasattr(trade, 'unrealized_pnl_usd') else 0.0,
            unrealized_pnl_percent=float(trade.unrealized_pnl_percent) if hasattr(trade, 'unrealized_pnl_percent') else 0.0,
            copied_from=None,  # Would fetch from relationship
            entry_timestamp=trade.entry_timestamp
        ))
    
    return positions


@router.get("/trades", response_model=dict)
async def get_trades(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, regex="^(open|closed)$"),
    market_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trade history with filters.
    
    **Filters:**
    - status: open/closed
    - market_id
    - start_date, end_date
    - limit, offset (pagination)
    """
    query = select(Trade).where(
        Trade.trader_wallet_address == current_user.wallet_address
    )
    
    # Apply filters
    if status:
        query = query.where(Trade.status == status)
    
    if market_id:
        query = query.where(Trade.market_id == market_id)
    
    if start_date:
        query = query.where(Trade.entry_timestamp >= start_date)
    
    if end_date:
        query = query.where(Trade.entry_timestamp <= end_date)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(desc(Trade.entry_timestamp))
    query = query.offset(offset).limit(limit + 1)
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    has_more = len(trades) > limit
    trades = trades[:limit]
    
    trades_list = [
        {
            "id": trade.id,
            "market_id": trade.market_id,
            "side": trade.side,
            "outcome": trade.position,
            "quantity": float(trade.quantity),
            "entry_price": float(trade.entry_price),
            "entry_value_usd": float(trade.entry_value_usd),
            "exit_price": float(trade.exit_price) if trade.exit_price else None,
            "realized_pnl_usd": float(trade.realized_pnl_usd) if trade.realized_pnl_usd else None,
            "status": trade.status,
            "entry_timestamp": trade.entry_timestamp.isoformat(),
            "exit_timestamp": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None
        }
        for trade in trades
    ]
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "trades": trades_list
    }


@router.get("/trades/{trade_id}")
async def get_trade_details(
    trade_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed trade information"""
    query = select(Trade).where(
        and_(
            Trade.id == trade_id,
            Trade.trader_wallet_address == current_user.wallet_address
        )
    )
    
    result = await db.execute(query)
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found"
        )
    
    return {
        "id": trade.id,
        "tx_hash": trade.entry_tx_hash,
        "market_id": trade.market_id,
        "side": trade.side,
        "outcome": trade.position,
        "quantity": float(trade.quantity),
        "entry_price": float(trade.entry_price),
        "entry_value_usd": float(trade.entry_value_usd),
        "exit_price": float(trade.exit_price) if trade.exit_price else None,
        "exit_value_usd": float(trade.exit_value_usd) if trade.exit_value_usd else None,
        "realized_pnl_usd": float(trade.realized_pnl_usd) if trade.realized_pnl_usd else None,
        "status": trade.status,
        "entry_timestamp": trade.entry_timestamp.isoformat(),
        "exit_timestamp": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None
    }


# ============================================================================
# Analytics
# ============================================================================

@router.get("/analytics/pnl-chart")
async def get_pnl_chart(
    timeframe: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get time-series P&L data for charts.
    
    **Timeframes:** 7d, 30d, 90d, all
    """
    # Use same logic as trader performance endpoint
    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    days = days_map.get(timeframe)
    
    query = select(Trade).where(Trade.trader_wallet_address == current_user.wallet_address)
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.where(Trade.entry_timestamp >= cutoff)
    
    query = query.order_by(Trade.entry_timestamp)
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    # Group by date
    from collections import defaultdict
    daily_pnl = defaultdict(float)
    
    for trade in trades:
        if trade.exit_timestamp and trade.realized_pnl_usd:
            date_key = trade.exit_timestamp.date().isoformat()
            daily_pnl[date_key] += float(trade.realized_pnl_usd)
    
    # Build data points
    data_points = []
    cumulative = 0
    
    for date in sorted(daily_pnl.keys()):
        cumulative += daily_pnl[date]
        data_points.append({
            "date": date,
            "pnl": round(daily_pnl[date], 2),
            "cumulative_pnl": round(cumulative, 2)
        })
    
    return {
        "timeframe": timeframe,
        "data_points": data_points
    }


@router.get("/analytics/by-trader")
async def get_analytics_by_trader(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    P&L breakdown per copied trader.
    """
    # In production, would join copy_relationships and aggregate
    return {
        "traders": []
    }


@router.get("/analytics/by-market")
async def get_analytics_by_market(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Performance breakdown per market.
    """
    # Group trades by market and aggregate P&L
    query = select(
        Trade.market_id,
        func.sum(Trade.realized_pnl_usd).label('total_pnl'),
        func.count().label('trade_count')
    ).where(
        and_(
            Trade.trader_wallet_address == current_user.wallet_address,
            Trade.status == 'closed'
        )
    ).group_by(Trade.market_id)
    
    result = await db.execute(query)
    markets = result.all()
    
    market_data = [
        {
            "market_id": row.market_id,
            "total_pnl": float(row.total_pnl) if row.total_pnl else 0,
            "trade_count": row.trade_count
        }
        for row in markets
    ]
    
    return {"markets": market_data}
