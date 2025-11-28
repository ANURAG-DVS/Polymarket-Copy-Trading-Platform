"""
Market Data Cache Service

Caches Polymarket market information and prices with:
- Redis-backed storage
- Automatic refresh (1-minute TTL)
- Graceful degradation on cache failure
- Cache warming on startup
"""

import asyncio
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings
from app.services.polymarket import get_polymarket_client


@dataclass
class MarketInfo:
    """Cached market information"""
    market_id: str
    name: str
    question: str
    end_date: datetime
    
    # Current prices
    yes_price: Decimal
    no_price: Decimal
    
    # Metadata
    volume_24h: Decimal = Decimal('0')
    liquidity: Decimal = Decimal('0')
    is_active: bool = True
    
    # Cache metadata
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'market_id': self.market_id,
            'name': self.name,
            'question': self.question,
            'end_date': self.end_date.isoformat(),
            'yes_price': float(self.yes_price),
            'no_price': float(self.no_price),
            'volume_24h': float(self.volume_24h),
            'liquidity': float(self.liquidity),
            'is_active': self.is_active,
            'last_updated': self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketInfo':
        """Create from dictionary"""
        return cls(
            market_id=data['market_id'],
            name=data['name'],
            question=data['question'],
            end_date=datetime.fromisoformat(data['end_date']),
            yes_price=Decimal(str(data['yes_price'])),
            no_price=Decimal(str(data['no_price'])),
            volume_24h=Decimal(str(data.get('volume_24h', 0))),
            liquidity=Decimal(str(data.get('liquidity', 0))),
            is_active=data.get('is_active', True),
            last_updated=datetime.fromisoformat(data['last_updated'])
        )


class MarketCacheService:
    """
    Cache service for Polymarket market data.
    
    Example:
        ```python
        cache = MarketCacheService()
        await cache.connect()
        
        # Warm cache on startup
        await cache.warm_cache()
        
        # Get market from cache
        market = await cache.get_market("0x123...")
        if market:
            print(f"{market.name}: YES ${market.yes_price}")
        ```
    """
    
    # Cache keys
    MARKET_PREFIX = "market"
    MARKETS_LIST_KEY = "markets:all"
    TRENDING_KEY = "markets:trending"
    PRICES_CHANNEL = "market:prices"
    
    # Configuration
    MARKET_TTL = 60  # 1 minute for individual markets
    LIST_TTL = 60  # 1 minute for market list
    PRICE_TTL = 10  # 10 seconds for prices
    
    def __init__(self):
        """Initialize market cache service"""
        self.redis_client: Optional[redis.Redis] = None
        self.polymarket_client = get_polymarket_client()
        
        # Metrics
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.cache_errors: int = 0
        
        # Background tasks
        self._refresh_task: Optional[asyncio.Task] = None
        
        logger.info("MarketCacheService initialized")
    
    async def connect(self):
        """Connect to Redis"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis for market cache")
    
    async def warm_cache(self):
        """
        Warm cache on startup by fetching all active markets.
        """
        logger.info("Warming market cache...")
        
        try:
            # Fetch all markets from Polymarket API
            markets = await self.polymarket_client.get_markets()
            
            logger.info(f"Fetched {len(markets)} markets from API")
            
            # Cache each market
            cached_count = 0
            for market_data in markets:
                try:
                    market_info = MarketInfo(
                        market_id=market_data.market_id,
                        name=market_data.name,
                        question=market_data.question,
                        end_date=market_data.end_date,
                        yes_price=market_data.yes_price,
                        no_price=market_data.no_price,
                        volume_24h=market_data.volume_24h,
                        liquidity=market_data.liquidity,
                        is_active=market_data.is_active
                    )
                    
                    await self._cache_market(market_info)
                    cached_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to cache market {market_data.market_id}: {e}")
            
            # Update markets list
            await self._update_markets_list([m.market_id for m in markets])
            
            logger.info(f"Cache warmed: {cached_count}/{len(markets)} markets cached")
            
        except Exception as e:
            logger.error(f"Failed to warm cache: {e}")
            # Graceful degradation - continue without cache
    
    async def get_market(
        self,
        market_id: str,
        use_cache: bool = True
    ) -> Optional[MarketInfo]:
        """
        Get market information.
        
        Args:
            market_id: Market ID
            use_cache: Use cache if available
            
        Returns:
            MarketInfo or None if not found
        """
        # Try cache first
        if use_cache:
            cached = await self._get_from_cache(market_id)
            if cached:
                self.cache_hits += 1
                return cached
            
            self.cache_misses += 1
        
        # Fallback to API
        try:
            market_data = await self.polymarket_client.get_market_by_id(market_id)
            
            if not market_data:
                return None
            
            market_info = MarketInfo(
                market_id=market_data.market_id,
                name=market_data.name,
                question=market_data.question,
                end_date=market_data.end_date,
                yes_price=market_data.yes_price,
                no_price=market_data.no_price,
                volume_24h=market_data.volume_24h,
                liquidity=market_data.liquidity,
                is_active=market_data.is_active
            )
            
            # Cache for future requests
            await self._cache_market(market_info)
            
            return market_info
            
        except Exception as e:
            logger.error(f"Failed to fetch market {market_id}: {e}")
            return None
    
    async def get_all_markets(self, use_cache: bool = True) -> List[MarketInfo]:
        """
        Get all active markets.
        
        Args:
            use_cache: Use cache if available
            
        Returns:
            List of MarketInfo
        """
        await self.connect()
        
        # Try cache first
        if use_cache:
            try:
                cached_ids = await self.redis_client.smembers(self.MARKETS_LIST_KEY)
                
                if cached_ids:
                    self.cache_hits += 1
                    
                    # Fetch each market from cache
                    markets = []
                    for market_id in cached_ids:
                        market = await self._get_from_cache(market_id)
                        if market:
                            markets.append(market)
                    
                    return markets
                
            except Exception as e:
                logger.error(f"Cache error: {e}")
                self.cache_errors += 1
        
        self.cache_misses += 1
        
        # Fallback to API
        try:
            markets_data = await self.polymarket_client.get_markets()
            
            markets = []
            for market_data in markets_data:
                market_info = MarketInfo(
                    market_id=market_data.market_id,
                    name=market_data.name,
                    question=market_data.question,
                    end_date=market_data.end_date,
                    yes_price=market_data.yes_price,
                    no_price=market_data.no_price,
                    volume_24h=market_data.volume_24h,
                    liquidity=market_data.liquidity,
                    is_active=market_data.is_active
                )
                
                markets.append(market_info)
                await self._cache_market(market_info)
            
            # Update markets list
            await self._update_markets_list([m.market_id for m in markets_data])
            
            return markets
            
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    async def get_market_price(
        self,
        market_id: str
    ) -> Optional[Dict[str, Decimal]]:
        """
        Get current market prices.
        
        Args:
            market_id: Market ID
            
        Returns:
            Dict with yes_price and no_price
        """
        # Try price-specific cache first (shorter TTL)
        price_key = f"price:{market_id}"
        
        try:
            await self.connect()
            cached_price = await self.redis_client.get(price_key)
            
            if cached_price:
                self.cache_hits += 1
                data = json.loads(cached_price)
                return {
                    'yes_price': Decimal(str(data['yes_price'])),
                    'no_price': Decimal(str(data['no_price']))
                }
        except Exception as e:
            logger.error(f"Price cache error: {e}")
        
        self.cache_misses += 1
        
        # Fetch from API
        try:
            prices = await self.polymarket_client.get_market_prices(market_id)
            
            price_data = {
                'yes_price': float(prices.yes_price),
                'no_price': float(prices.no_price)
            }
            
            # Cache with short TTL
            try:
                await self.redis_client.setex(
                    price_key,
                    self.PRICE_TTL,
                    json.dumps(price_data)
                )
                
                # Publish price update
                await self._publish_price_update(market_id, prices)
                
            except Exception as e:
                logger.error(f"Failed to cache price: {e}")
            
            return {
                'yes_price': prices.yes_price,
                'no_price': prices.no_price
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch price for {market_id}: {e}")
            return None
    
    async def get_trending_markets(self, limit: int = 10) -> List[MarketInfo]:
        """
        Get trending markets (sorted by 24h volume).
        
        Args:
            limit: Number of markets to return
            
        Returns:
            List of trending MarketInfo
        """
        # Get all markets
        markets = await self.get_all_markets()
        
        # Sort by 24h volume
        trending = sorted(
            markets,
            key=lambda m: m.volume_24h,
            reverse=True
        )[:limit]
        
        return trending
    
    async def invalidate_market(self, market_id: str):
        """
        Invalidate cache for a specific market.
        
        Args:
            market_id: Market ID to invalidate
        """
        try:
            await self.connect()
            
            # Delete market cache
            market_key = f"{self.MARKET_PREFIX}:{market_id}"
            await self.redis_client.delete(market_key)
            
            # Delete price cache
            price_key = f"price:{market_id}"
            await self.redis_client.delete(price_key)
            
            # Remove from markets list
            await self.redis_client.srem(self.MARKETS_LIST_KEY, market_id)
            
            logger.info(f"Invalidated cache for market {market_id}")
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
    
    async def start_auto_refresh(self):
        """Start background task for auto-refreshing cache"""
        if self._refresh_task:
            logger.warning("Auto-refresh already running")
            return
        
        self._refresh_task = asyncio.create_task(self._auto_refresh_loop())
        logger.info("Started auto-refresh task")
    
    async def stop_auto_refresh(self):
        """Stop background refresh task"""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            
            self._refresh_task = None
            logger.info("Stopped auto-refresh task")
    
    async def _auto_refresh_loop(self):
        """Background loop to refresh cache periodically"""
        while True:
            try:
                await asyncio.sleep(60)  # 1 minute
                
                logger.debug("Auto-refreshing market cache...")
                await self.warm_cache()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-refresh error: {e}")
    
    async def _cache_market(self, market: MarketInfo):
        """Cache a market"""
        try:
            await self.connect()
            
            market_key = f"{self.MARKET_PREFIX}:{market.market_id}"
            
            await self.redis_client.setex(
                market_key,
                self.MARKET_TTL,
                json.dumps(market.to_dict())
            )
            
        except Exception as e:
            logger.error(f"Failed to cache market: {e}")
            self.cache_errors += 1
    
    async def _get_from_cache(self, market_id: str) -> Optional[MarketInfo]:
        """Get market from cache"""
        try:
            await self.connect()
            
            market_key = f"{self.MARKET_PREFIX}:{market_id}"
            cached = await self.redis_client.get(market_key)
            
            if cached:
                data = json.loads(cached)
                return MarketInfo.from_dict(data)
            
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            self.cache_errors += 1
        
        return None
    
    async def _update_markets_list(self, market_ids: List[str]):
        """Update list of all market IDs"""
        try:
            await self.connect()
            
            # Clear existing list
            await self.redis_client.delete(self.MARKETS_LIST_KEY)
            
            # Add all market IDs
            if market_ids:
                await self.redis_client.sadd(self.MARKETS_LIST_KEY, *market_ids)
                await self.redis_client.expire(self.MARKETS_LIST_KEY, self.LIST_TTL)
            
        except Exception as e:
            logger.error(f"Failed to update markets list: {e}")
    
    async def _publish_price_update(self, market_id: str, prices: Any):
        """Publish price update to Redis pub/sub"""
        try:
            await self.connect()
            
            update = {
                'market_id': market_id,
                'yes_price': float(prices.yes_price),
                'no_price': float(prices.no_price),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.redis_client.publish(
                self.PRICES_CHANNEL,
                json.dumps(update)
            )
            
        except Exception as e:
            logger.error(f"Failed to publish price update: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (
            (self.cache_hits / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_errors': self.cache_errors,
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests
        }
    
    async def close(self):
        """Close connections"""
        await self.stop_auto_refresh()
        
        if self.redis_client:
            await self.redis_client.close()


# Singleton instance
_market_cache_service: Optional[MarketCacheService] = None


def get_market_cache_service() -> MarketCacheService:
    """Get singleton instance of MarketCacheService"""
    global _market_cache_service
    if _market_cache_service is None:
        _market_cache_service = MarketCacheService()
    return _market_cache_service
