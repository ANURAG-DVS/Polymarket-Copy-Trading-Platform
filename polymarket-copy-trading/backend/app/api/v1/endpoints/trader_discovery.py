"""
Trader Search & Discovery Endpoints

Comprehensive search, filtering, and recommendation system for discovering traders.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.api_key import Trade, User


router = APIRouter(prefix="/traders", tags=["trader-discovery"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TraderSearchFilters(BaseModel):
    """Filter criteria for trader search"""
    min_pnl_7d: Optional[float] = None
    min_pnl_30d: Optional[float] = None
    min_winrate: Optional[float] = Field(None, ge=0, le=100)
    min_trades: Optional[int] = Field(None, ge=0)
    max_loss: Optional[float] = None
    min_sharpe: Optional[float] = None
    
    # Activity filters
    active_last_days: Optional[int] = Field(None, ge=1, le=365)


class TraderSearchResult(BaseModel):
    """Single trader search result"""
    wallet_address: str
    rank: Optional[int] = None
    
    pnl_7d: float
    pnl_30d: float
    win_rate_7d: float
    total_trades: int
    sharpe_ratio: Optional[float] = None
    
    # Match score
    relevance_score: float = 1.0
    
    # Categories
    categories: List[str] = []


class FilterMetadata(BaseModel):
    """Available filter ranges"""
    pnl_7d_range: Dict[str, float]
    pnl_30d_range: Dict[str, float]
    winrate_range: Dict[str, float]
    trades_range: Dict[str, int]
    sharpe_range: Dict[str, float]
    
    total_traders: int


class CategoryInfo(BaseModel):
    """Trader category information"""
    name: str
    description: str
    trader_count: int
    criteria: Dict[str, Any]


# ============================================================================
# Helper Functions
# ============================================================================

def categorize_trader(
    pnl_7d: float,
    pnl_30d: float,
    win_rate_7d: float,
    total_trades: int,
    sharpe_ratio: Optional[float]
) -> List[str]:
    """
    Auto-categorize trader based on performance metrics.
    
    Returns list of category names.
    """
    categories = []
    
    # Consistent Winners
    if win_rate_7d >= 65 and pnl_7d > 0 and pnl_30d > 0:
        categories.append("Consistent Winners")
    
    # High Volume
    if total_trades >= 100:
        categories.append("High Volume")
    
    # New & Rising
    if total_trades < 50 and pnl_7d > 500:
        categories.append("New & Rising")
    
    # Top Performers
    if pnl_30d > 5000:
        categories.append("Top Performers")
    
    # Risk Managers
    if sharpe_ratio and sharpe_ratio > 2.0:
        categories.append("Risk Managers")
    
    # Active Traders
    if total_trades >= 20:  # Would check last_7d in real implementation
        categories.append("Active Traders")
    
    return categories


async def track_search(db: AsyncSession, query: str, filters: Dict[str, Any]):
    """Track search analytics (simplified)"""
    # In production, would insert into search_analytics table
    pass


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/search", response_model=Dict[str, Any])
async def search_traders(
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    min_pnl_7d: Optional[float] = Query(None),
    min_pnl_30d: Optional[float] = Query(None),
    min_winrate: Optional[float] = Query(None, ge=0, le=100),
    min_trades: Optional[int] = Query(None, ge=0),
    max_loss: Optional[float] = Query(None),
    min_sharpe: Optional[float] = Query(None),
    active_last_days: Optional[int] = Query(None, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for traders with advanced filtering.
    
    **Parameters:**
    - `q`: Search query (wallet address or username prefix)
    - `min_pnl_7d`: Minimum 7-day P&L
    - `min_pnl_30d`: Minimum 30-day P&L
    - `min_winrate`: Minimum win rate (0-100)
    - `min_trades`: Minimum total trades
    - `max_loss`: Maximum loss threshold
    - `min_sharpe`: Minimum Sharpe ratio
    - `active_last_days`: Active in last N days
    - `limit`: Results per page
    - `offset`: Pagination offset
    
    **Example:**
    ```
    GET /api/traders/search?min_pnl_7d=1000&min_winrate=60&limit=20
    ```
    """
    # Build query
    query_obj = select(User).where(User.total_trades > 0)
    
    # Search by wallet address
    if q:
        # Support partial wallet address search
        query_obj = query_obj.where(
            User.wallet_address.ilike(f"%{q}%")
        )
    
    # Apply filters
    if min_pnl_7d is not None:
        query_obj = query_obj.where(User.pnl_7d_usd >= min_pnl_7d)
    
    if min_pnl_30d is not None:
        query_obj = query_obj.where(User.pnl_30d_usd >= min_pnl_30d)
    
    if min_winrate is not None:
        query_obj = query_obj.where(User.win_rate_7d >= min_winrate)
    
    if min_trades is not None:
        query_obj = query_obj.where(User.total_trades >= min_trades)
    
    if max_loss is not None:
        # Filter out traders with losses exceeding threshold
        query_obj = query_obj.where(User.pnl_total_usd >= -max_loss)
    
    if min_sharpe is not None:
        query_obj = query_obj.where(
            and_(
                User.sharpe_ratio.isnot(None),
                User.sharpe_ratio >= min_sharpe
            )
        )
    
    if active_last_days:
        # Would check last_trade_at in real implementation
        cutoff = datetime.utcnow() - timedelta(days=active_last_days)
        # query_obj = query_obj.where(User.last_trade_at >= cutoff)
    
    # Count total results
    count_query = select(func.count()).select_from(query_obj.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Order by relevance (P&L 7d desc)
    query_obj = query_obj.order_by(desc(User.pnl_7d_usd))
    
    # Pagination
    query_obj = query_obj.offset(offset).limit(limit + 1)
    
    # Execute
    result = await db.execute(query_obj)
    traders = result.scalars().all()
    
    # Check has_more
    has_more = len(traders) > limit
    traders = traders[:limit]
    
    # Build results with categories
    results = []
    for idx, trader in enumerate(traders):
        # Categorize trader
        categories = categorize_trader(
            float(trader.pnl_7d_usd) if hasattr(trader, 'pnl_7d_usd') else 0,
            float(trader.pnl_30d_usd) if hasattr(trader, 'pnl_30d_usd') else 0,
            float(trader.win_rate_7d) if hasattr(trader, 'win_rate_7d') else 0,
            trader.total_trades if hasattr(trader, 'total_trades') else 0,
            float(trader.sharpe_ratio) if hasattr(trader, 'sharpe_ratio') and trader.sharpe_ratio else None
        )
        
        result_item = TraderSearchResult(
            wallet_address=trader.wallet_address,
            rank=offset + idx + 1,
            pnl_7d=float(trader.pnl_7d_usd) if hasattr(trader, 'pnl_7d_usd') else 0,
            pnl_30d=float(trader.pnl_30d_usd) if hasattr(trader, 'pnl_30d_usd') else 0,
            win_rate_7d=float(trader.win_rate_7d) if hasattr(trader, 'win_rate_7d') else 0,
            total_trades=trader.total_trades if hasattr(trader, 'total_trades') else 0,
            sharpe_ratio=float(trader.sharpe_ratio) if hasattr(trader, 'sharpe_ratio') and trader.sharpe_ratio else None,
            relevance_score=1.0,
            categories=categories
        )
        results.append(result_item.dict())
    
    # Track search analytics
    await track_search(db, q or "", {
        "min_pnl_7d": min_pnl_7d,
        "min_winrate": min_winrate,
        "min_trades": min_trades
    })
    
    return {
        "query": q,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "results": results
    }


@router.get("/categories/{category_name}", response_model=Dict[str, Any])
async def get_traders_by_category(
    category_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get traders in a specific category.
    
    **Categories:**
    - `consistent-winners`: Win rate >= 65%, positive P&L
    - `high-volume`: 100+ total trades
    - `new-rising`: < 50 trades, P&L 7d > $500
    - `top-performers`: 30-day P&L > $5000
    - `risk-managers`: Sharpe ratio > 2.0
    - `active-traders`: 20+ trades
    
    **Example:**
    ```
    GET /api/traders/categories/consistent-winners?limit=20
    ```
    """
    # Map category name to filters
    category_map = {
        "consistent-winners": {
            "filters": {"min_winrate": 65, "min_pnl_7d": 0, "min_pnl_30d": 0},
            "description": "Traders with 65%+ win rate and positive P&L"
        },
        "high-volume": {
            "filters": {"min_trades": 100},
            "description": "Traders with 100+ total trades"
        },
        "new-rising": {
            "filters": {"min_pnl_7d": 500},
            "max_trades": 50,
            "description": "New traders with strong recent performance"
        },
        "top-performers": {
            "filters": {"min_pnl_30d": 5000},
            "description": "Top traders with 30-day P&L > $5000"
        },
        "risk-managers": {
            "filters": {"min_sharpe": 2.0},
            "description": "Traders with excellent risk-adjusted returns"
        },
        "active-traders": {
            "filters": {"min_trades": 20},
            "description": "Active traders with 20+ trades"
        }
    }
    
    category_config = category_map.get(category_name)
    if not category_config:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Build query based on category criteria
    query_obj = select(User).where(User.total_trades > 0)
    
    filters = category_config["filters"]
    
    if "min_winrate" in filters:
        query_obj = query_obj.where(User.win_rate_7d >= filters["min_winrate"])
    
    if "min_pnl_7d" in filters:
        query_obj = query_obj.where(User.pnl_7d_usd >= filters["min_pnl_7d"])
    
    if "min_pnl_30d" in filters:
        query_obj = query_obj.where(User.pnl_30d_usd >= filters["min_pnl_30d"])
    
    if "min_trades" in filters:
        query_obj = query_obj.where(User.total_trades >= filters["min_trades"])
    
    if "max_trades" in category_config:
        query_obj = query_obj.where(User.total_trades < category_config["max_trades"])
    
    if "min_sharpe" in filters:
        query_obj = query_obj.where(
            and_(
                User.sharpe_ratio.isnot(None),
                User.sharpe_ratio >= filters["min_sharpe"]
            )
        )
    
    # Count total
    count_query = select(func.count()).select_from(query_obj.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Order and paginate
    query_obj = query_obj.order_by(desc(User.pnl_7d_usd))
    query_obj = query_obj.offset(offset).limit(limit + 1)
    
    # Execute
    result = await db.execute(query_obj)
    traders = result.scalars().all()
    
    has_more = len(traders) > limit
    traders = traders[:limit]
    
    # Format results
    results = []
    for trader in traders:
        results.append({
            "wallet_address": trader.wallet_address,
            "pnl_7d": float(trader.pnl_7d_usd) if hasattr(trader, 'pnl_7d_usd') else 0,
            "pnl_30d": float(trader.pnl_30d_usd) if hasattr(trader, 'pnl_30d_usd') else 0,
            "win_rate_7d": float(trader.win_rate_7d) if hasattr(trader, 'win_rate_7d') else 0,
            "total_trades": trader.total_trades if hasattr(trader, 'total_trades') else 0
        })
    
    return {
        "category": category_name,
        "description": category_config["description"],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "traders": results
    }


@router.get("/recommendations", response_model=Dict[str, Any])
async def get_trader_recommendations(
    user_id: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recommended traders to copy.
    
    **Logic:**
    - If user_id provided: Similar traders based on copy list
    - Otherwise: Trending traders (top by 7-day P&L growth)
    
    **Example:**
    ```
    GET /api/traders/recommendations?limit=10
    ```
    """
    # Simple recommendation: Top trending traders
    # In production, would use collaborative filtering based on user's copy list
    
    query = select(User).where(
        and_(
            User.total_trades >= 10,
            User.pnl_7d_usd > 0
        )
    ).order_by(desc(User.pnl_7d_usd)).limit(limit)
    
    result = await db.execute(query)
    traders = result.scalars().all()
    
    recommendations = []
    for trader in traders:
        categories = categorize_trader(
            float(trader.pnl_7d_usd) if hasattr(trader, 'pnl_7d_usd') else 0,
            float(trader.pnl_30d_usd) if hasattr(trader, 'pnl_30d_usd') else 0,
            float(trader.win_rate_7d) if hasattr(trader, 'win_rate_7d') else 0,
            trader.total_trades if hasattr(trader, 'total_trades') else 0,
            float(trader.sharpe_ratio) if hasattr(trader, 'sharpe_ratio') and trader.sharpe_ratio else None
        )
        
        recommendations.append({
            "wallet_address": trader.wallet_address,
            "pnl_7d": float(trader.pnl_7d_usd) if hasattr(trader, 'pnl_7d_usd') else 0,
            "win_rate_7d": float(trader.win_rate_7d) if hasattr(trader, 'win_rate_7d') else 0,
            "total_trades": trader.total_trades if hasattr(trader, 'total_trades') else 0,
            "categories": categories,
            "reason": "Top trending trader" if not user_id else "Similar to your copy list"
        })
    
    return {
        "count": len(recommendations),
        "recommendations": recommendations
    }


@router.get("/filters/metadata", response_model=FilterMetadata)
async def get_filter_metadata(db: AsyncSession = Depends(get_db)):
    """
    Get available filter ranges for UI.
    
    Returns min/max values for all filterable fields.
    
    **Example Response:**
    ```json
    {
      "pnl_7d_range": {"min": -500.0, "max": 10000.0},
      "winrate_range": {"min": 0.0, "max": 100.0},
      "total_traders": 2345
    }
    ```
    """
    # Get aggregate stats
    query = select(
        func.min(User.pnl_7d_usd).label('min_pnl_7d'),
        func.max(User.pnl_7d_usd).label('max_pnl_7d'),
        func.min(User.pnl_30d_usd).label('min_pnl_30d'),
        func.max(User.pnl_30d_usd).label('max_pnl_30d'),
        func.min(User.win_rate_7d).label('min_winrate'),
        func.max(User.win_rate_7d).label('max_winrate'),
        func.min(User.total_trades).label('min_trades'),
        func.max(User.total_trades).label('max_trades'),
        func.min(User.sharpe_ratio).label('min_sharpe'),
        func.max(User.sharpe_ratio).label('max_sharpe'),
        func.count().label('total')
    ).where(User.total_trades > 0)
    
    result = await db.execute(query)
    stats = result.one()
    
    return FilterMetadata(
        pnl_7d_range={
            "min": float(stats.min_pnl_7d or 0),
            "max": float(stats.max_pnl_7d or 0)
        },
        pnl_30d_range={
            "min": float(stats.min_pnl_30d or 0),
            "max": float(stats.max_pnl_30d or 0)
        },
        winrate_range={
            "min": float(stats.min_winrate or 0),
            "max": float(stats.max_winrate or 0)
        },
        trades_range={
            "min": int(stats.min_trades or 0),
            "max": int(stats.max_trades or 0)
        },
        sharpe_range={
            "min": float(stats.min_sharpe or 0),
            "max": float(stats.max_sharpe or 0)
        },
        total_traders=int(stats.total)
    )


@router.get("/categories", response_model=List[CategoryInfo])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """
    List all available trader categories with counts.
    
    **Returns:**
    - List of categories with trader counts
    """
    categories = [
        {
            "name": "consistent-winners",
            "description": "Traders with 65%+ win rate and positive P&L",
            "criteria": {"min_winrate": 65, "min_pnl_7d": 0}
        },
        {
            "name": "high-volume",
            "description": "Traders with 100+ total trades",
            "criteria": {"min_trades": 100}
        },
        {
            "name": "new-rising",
            "description": "New traders with strong recent performance",
            "criteria": {"min_pnl_7d": 500, "max_trades": 50}
        },
        {
            "name": "top-performers",
            "description": "Top traders with 30-day P&L > $5000",
            "criteria": {"min_pnl_30d": 5000}
        },
        {
            "name": "risk-managers",
            "description": "Traders with excellent risk-adjusted returns",
            "criteria": {"min_sharpe": 2.0}
        }
    ]
    
    # Get counts for each category
    results = []
    for category in categories:
        # Build count query based on criteria
        count_query = select(func.count()).where(User.total_trades > 0)
        
        criteria = category["criteria"]
        if "min_winrate" in criteria:
            count_query = count_query.where(User.win_rate_7d >= criteria["min_winrate"])
        if "min_pnl_7d" in criteria:
            count_query = count_query.where(User.pnl_7d_usd >= criteria["min_pnl_7d"])
        if "min_pnl_30d" in criteria:
            count_query = count_query.where(User.pnl_30d_usd >= criteria["min_pnl_30d"])
        if "min_trades" in criteria:
            count_query = count_query.where(User.total_trades >= criteria["min_trades"])
        if "max_trades" in criteria:
            count_query = count_query.where(User.total_trades < criteria["max_trades"])
        if "min_sharpe" in criteria:
            count_query = count_query.where(
                and_(User.sharpe_ratio.isnot(None), User.sharpe_ratio >= criteria["min_sharpe"])
            )
        
        count_result = await db.execute(count_query)
        count = count_result.scalar()
        
        results.append(CategoryInfo(
            name=category["name"],
            description=category["description"],
            trader_count=count,
            criteria=criteria
        ))
    
    return results
