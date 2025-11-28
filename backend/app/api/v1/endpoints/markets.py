"""
Market Cache API Endpoints

FastAPI endpoints for accessing cached market data.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.cache.market_cache import get_market_cache_service, MarketInfo


router = APIRouter(prefix="/markets", tags=["markets"])


class MarketResponse(BaseModel):
    """Market information response"""
    market_id: str
    name: str
    question: str
    end_date: str
    yes_price: float
    no_price: float
    volume_24h: float
    liquidity: float
    is_active: bool
    last_updated: str


class PriceResponse(BaseModel):
    """Price response"""
    market_id: str
    yes_price: float
    no_price: float


class CacheMetricsResponse(BaseModel):
    """Cache metrics response"""
    cache_hits: int
    cache_misses: int
    cache_errors: int
    hit_rate: float
    total_requests: int


@router.get("/", response_model=list[MarketResponse])
async def get_markets(
    limit: Optional[int] = Query(None, ge=1, le=500),
    use_cache: bool = Query(True, description="Use cache if available")
):
    """
    Get all active markets.
    
    **Parameters:**
    - `limit`: Maximum markets to return (optional)
    - `use_cache`: Whether to use cache (default: true)
    
    **Returns:**
    - List of active markets with current prices
    
    **Example:**
    ```
    GET /api/v1/markets?limit=10
    ```
    """
    cache = get_market_cache_service()
    
    markets = await cache.get_all_markets(use_cache=use_cache)
    
    if limit:
        markets = markets[:limit]
    
    return [
        MarketResponse(**market.to_dict())
        for market in markets
    ]


@router.get("/trending", response_model=list[MarketResponse])
async def get_trending_markets(
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get trending markets (sorted by 24h volume).
    
    **Parameters:**
    - `limit`: Number of markets (default: 10)
    
    **Returns:**
    - List of trending markets
    """
    cache = get_market_cache_service()
    
    markets = await cache.get_trending_markets(limit=limit)
    
    return [
        MarketResponse(**market.to_dict())
        for market in markets
    ]


@router.get("/{market_id}", response_model=MarketResponse)
async def get_market(
    market_id: str,
    use_cache: bool = Query(True)
):
    """
    Get market details by ID.
    
    **Parameters:**
    - `market_id`: Market ID
    - `use_cache`: Use cache if available
    
    **Returns:**
    - Market information
    
    **Raises:**
    - 404: Market not found
    """
    cache = get_market_cache_service()
    
    market = await cache.get_market(market_id, use_cache=use_cache)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return MarketResponse(**market.to_dict())


@router.get("/{market_id}/price", response_model=PriceResponse)
async def get_market_price(market_id: str):
    """
    Get current market prices.
    
    **Parameters:**
    - `market_id`: Market ID
    
    **Returns:**
    - Current YES and NO prices
    
    **Example:**
    ```json
    {
      "market_id": "0x123...",
      "yes_price": 0.65,
      "no_price": 0.35
    }
    ```
    """
    cache = get_market_cache_service()
    
    prices = await cache.get_market_price(market_id)
    
    if not prices:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return PriceResponse(
        market_id=market_id,
        yes_price=float(prices['yes_price']),
        no_price=float(prices['no_price'])
    )


@router.post("/{market_id}/invalidate")
async def invalidate_market_cache(market_id: str):
    """
    Invalidate cache for a specific market.
    
    **Parameters:**
    - `market_id`: Market ID to invalidate
    
    **Returns:**
    - Success message
    """
    cache = get_market_cache_service()
    
    await cache.invalidate_market(market_id)
    
    return {"message": f"Cache invalidated for market {market_id}"}


@router.get("/metrics/cache", response_model=CacheMetricsResponse)
async def get_cache_metrics():
    """
    Get cache performance metrics.
    
    **Returns:**
    - Cache hit/miss statistics
    
    **Example:**
    ```json
    {
      "cache_hits": 1542,
      "cache_misses": 89,
      "cache_errors": 2,
      "hit_rate": 94.54,
      "total_requests": 1631
    }
    ```
    """
    cache = get_market_cache_service()
    
    metrics = cache.get_metrics()
    
    return CacheMetricsResponse(**metrics)
