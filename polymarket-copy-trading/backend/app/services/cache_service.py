"""
Redis caching service for trader data and leaderboards.

Provides a comprehensive caching layer with:
- Leaderboard caching with configurable TTL
- Trader details caching
- Batch operations for performance
- Cache invalidation strategies
- Graceful degradation on Redis failures
- Performance metrics and monitoring

Caching Strategy:
- Write-through: Update cache on database writes
- TTL-based expiration: Auto-expire stale data
- Pattern-based invalidation: Bulk cache clearing
"""

import logging
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for managing Redis cache operations.
    
    Features:
    - Connection pooling for performance
    - Circuit breaker pattern for reliability
    - Automatic serialization/deserialization
    - Cache key generation with hashing
    - Batch operations support
    - Cache statistics tracking
    """
    
    # Cache key prefixes
    PREFIX_LEADERBOARD = "leaderboard"
    PREFIX_TRADER = "trader"
    PREFIX_TRADER_STATS = "trader_stats"
    PREFIX_TRADER_POSITIONS = "trader_positions"
    
    # Default TTL values (seconds)
    TTL_LEADERBOARD = 60  # 1 minute
    TTL_TRADER = 300  # 5 minutes
    TTL_STATS = 180  # 3 minutes
    
    # Circuit breaker settings
    MAX_FAILURES = 5
    FAILURE_RESET_TIME = 60  # seconds
    
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        """
        Initialize cache service.
        
        Args:
            redis_client: Optional Redis client instance (will create if not provided)
        """
        self.redis = redis_client
        self._failures = 0
        self._last_failure_time: Optional[datetime] = None
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """
        Get Redis client with circuit breaker pattern.
        
        Returns:
            Redis client or None if circuit is open
        """
        # Check circuit breaker
        if self._failures >= self.MAX_FAILURES:
            if self._last_failure_time:
                time_since_failure = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if time_since_failure < self.FAILURE_RESET_TIME:
                    logger.warning(f"Circuit breaker open: {self._failures} failures")
                    return None
                else:
                    # Reset circuit breaker
                    logger.info("Circuit breaker reset")
                    self._failures = 0
                    self._last_failure_time = None
        
        # Create Redis client if not exists
        if not self.redis:
            try:
                self.redis = await aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=10,
                    socket_timeout=2.0,
                    socket_connect_timeout=2.0
                )
            except Exception as e:
                logger.error(f"Failed to create Redis client: {e}")
                self._record_failure()
                return None
        
        return self.redis
    
    def _record_failure(self):
        """Record a cache failure for circuit breaker."""
        self._failures += 1
        self._last_failure_time = datetime.utcnow()
        logger.warning(f"Cache failure recorded: {self._failures}/{self.MAX_FAILURES}")
    
    # ========================================================================
    # Leaderboard Caching
    # ========================================================================
    
    async def get_cached_leaderboard(
        self,
        timeframe: str,
        filters: Dict[str, Any]
    ) -> Optional[List[Dict]]:
        """
        Retrieve leaderboard from cache.
        
        Args:
            timeframe: Time window (7d, 30d, all)
            filters: Query filters (limit, offset, min_trades, etc.)
            
        Returns:
            Cached leaderboard data or None if cache miss
            
        Example:
            >>> cache = CacheService()
            >>> data = await cache.get_cached_leaderboard("7d", {"limit": 100})
        """
        redis = await self._get_redis()
        if not redis:
            return None
        
        try:
            # Generate cache key
            key = self._generate_cache_key(
                self.PREFIX_LEADERBOARD,
                {"timeframe": timeframe, **filters}
            )
            
            # Get from cache
            cached = await redis.get(key)
            
            if cached:
                self._cache_hits += 1
                logger.debug(f"Cache HIT: {key}")
                return self._deserialize_data(cached)
            else:
                self._cache_misses += 1
                logger.debug(f"Cache MISS: {key}")
                return None
                
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in get_cached_leaderboard: {e}")
            self._record_failure()
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_cached_leaderboard: {e}")
            return None
    
    async def set_cached_leaderboard(
        self,
        timeframe: str,
        filters: Dict[str, Any],
        data: List[Dict],
        ttl: int = TTL_LEADERBOARD
    ) -> bool:
        """
        Store leaderboard in cache with TTL.
        
        Args:
            timeframe: Time window
            filters: Query filters
            data: Leaderboard data to cache
            ttl: Time-to-live in seconds (default: 60)
            
        Returns:
            True if successful, False otherwise
        """
        redis = await self._get_redis()
        if not redis:
            return False
        
        try:
            # Generate cache key
            key = self._generate_cache_key(
                self.PREFIX_LEADERBOARD,
                {"timeframe": timeframe, **filters}
            )
            
            # Serialize and store
            serialized = self._serialize_data(data)
            await redis.setex(key, ttl, serialized)
            
            logger.debug(f"Cached leaderboard: {key} (TTL: {ttl}s)")
            return True
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in set_cached_leaderboard: {e}")
            self._record_failure()
            return False
        except Exception as e:
            logger.error(f"Unexpected error in set_cached_leaderboard: {e}")
            return False
    
    # ========================================================================
    # Trader Details Caching
    # ========================================================================
    
    async def get_cached_trader(
        self,
        wallet_address: str
    ) -> Optional[Dict]:
        """
        Get trader details from cache.
        
        Args:
            wallet_address: Ethereum wallet address
            
        Returns:
            Cached trader data or None
        """
        redis = await self._get_redis()
        if not redis:
            return None
        
        try:
            key = f"{self.PREFIX_TRADER}:{wallet_address.lower()}"
            cached = await redis.get(key)
            
            if cached:
                self._cache_hits += 1
                logger.debug(f"Cache HIT: trader {wallet_address}")
                return self._deserialize_data(cached)
            else:
                self._cache_misses += 1
                return None
                
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in get_cached_trader: {e}")
            self._record_failure()
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_cached_trader: {e}")
            return None
    
    async def set_cached_trader(
        self,
        wallet_address: str,
        data: Dict,
        ttl: int = TTL_TRADER
    ) -> bool:
        """
        Cache trader details (5-minute TTL by default).
        
        Args:
            wallet_address: Ethereum wallet address
            data: Trader data to cache
            ttl: Time-to-live in seconds (default: 300)
            
        Returns:
            True if successful
        """
        redis = await self._get_redis()
        if not redis:
            return False
        
        try:
            key = f"{self.PREFIX_TRADER}:{wallet_address.lower()}"
            serialized = self._serialize_data(data)
            await redis.setex(key, ttl, serialized)
            
            logger.debug(f"Cached trader: {wallet_address} (TTL: {ttl}s)")
            return True
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in set_cached_trader: {e}")
            self._record_failure()
            return False
        except Exception as e:
            logger.error(f"Unexpected error in set_cached_trader: {e}")
            return False
    
    # ========================================================================
    # Cache Invalidation
    # ========================================================================
    
    async def invalidate_trader_cache(
        self,
        wallet_address: str
    ) -> None:
        """
        Invalidate all cache entries for a trader.
        
        Deletes:
        - Trader details
        - Trader stats
        - Trader positions
        
        Args:
            wallet_address: Ethereum wallet address
        """
        redis = await self._get_redis()
        if not redis:
            return
        
        try:
            # Build patterns for all trader-related keys
            patterns = [
                f"{self.PREFIX_TRADER}:{wallet_address.lower()}",
                f"{self.PREFIX_TRADER_STATS}:{wallet_address.lower()}*",
                f"{self.PREFIX_TRADER_POSITIONS}:{wallet_address.lower()}*",
            ]
            
            # Delete all matching keys
            for pattern in patterns:
                if '*' in pattern:
                    # Pattern match - need to scan
                    keys = await redis.keys(pattern)
                    if keys:
                        await redis.delete(*keys)
                else:
                    # Direct key delete
                    await redis.delete(pattern)
            
            logger.info(f"Invalidated cache for trader: {wallet_address}")
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in invalidate_trader_cache: {e}")
            self._record_failure()
        except Exception as e:
            logger.error(f"Unexpected error in invalidate_trader_cache: {e}")
    
    async def invalidate_leaderboard_cache(
        self,
        timeframe: Optional[str] = None
    ) -> None:
        """
        Invalidate leaderboard cache.
        
        Args:
            timeframe: Specific timeframe to invalidate (7d, 30d, all)
                      If None, invalidates all leaderboards
        """
        redis = await self._get_redis()
        if not redis:
            return
        
        try:
            if timeframe:
                # Invalidate specific timeframe
                pattern = f"{self.PREFIX_LEADERBOARD}:{timeframe}:*"
            else:
                # Invalidate all leaderboards
                pattern = f"{self.PREFIX_LEADERBOARD}:*"
            
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} leaderboard cache entries")
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in invalidate_leaderboard_cache: {e}")
            self._record_failure()
        except Exception as e:
            logger.error(f"Unexpected error in invalidate_leaderboard_cache: {e}")
    
    # ========================================================================
    # Batch Operations
    # ========================================================================
    
    async def mget_traders(
        self,
        wallet_addresses: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch multiple traders from cache in one operation.
        
        Args:
            wallet_addresses: List of wallet addresses
            
        Returns:
            Dictionary mapping addresses to cached data (or None)
            
        Example:
            >>> cache = CacheService()
            >>> traders = await cache.mget_traders(["0x123...", "0xabc..."])
            >>> print(traders["0x123..."])
        """
        redis = await self._get_redis()
        if not redis:
            return {addr: None for addr in wallet_addresses}
        
        try:
            # Build keys
            keys = [f"{self.PREFIX_TRADER}:{addr.lower()}" for addr in wallet_addresses]
            
            # Batch get
            values = await redis.mget(keys)
            
            # Build result mapping
            result = {}
            for addr, value in zip(wallet_addresses, values):
                if value:
                    self._cache_hits += 1
                    result[addr] = self._deserialize_data(value)
                else:
                    self._cache_misses += 1
                    result[addr] = None
            
            logger.debug(f"Batch fetched {len(wallet_addresses)} traders, {sum(1 for v in values if v)} hits")
            return result
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in mget_traders: {e}")
            self._record_failure()
            return {addr: None for addr in wallet_addresses}
        except Exception as e:
            logger.error(f"Unexpected error in mget_traders: {e}")
            return {addr: None for addr in wallet_addresses}
    
    async def mset_traders(
        self,
        traders_data: Dict[str, Dict],
        ttl: int = TTL_TRADER
    ) -> bool:
        """
        Store multiple traders in cache.
        
        Args:
            traders_data: Dictionary mapping wallet addresses to trader data
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful
        """
        redis = await self._get_redis()
        if not redis:
            return False
        
        try:
            # Use pipeline for atomic operation
            pipe = redis.pipeline()
            
            for addr, data in traders_data.items():
                key = f"{self.PREFIX_TRADER}:{addr.lower()}"
                serialized = self._serialize_data(data)
                pipe.setex(key, ttl, serialized)
            
            await pipe.execute()
            
            logger.debug(f"Batch cached {len(traders_data)} traders (TTL: {ttl}s)")
            return True
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error in mset_traders: {e}")
            self._record_failure()
            return False
        except Exception as e:
            logger.error(f"Unexpected error in mset_traders: {e}")
            return False
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _generate_cache_key(
        self,
        prefix: str,
        params: Dict[str, Any]
    ) -> str:
        """
        Generate consistent cache key from parameters.
        
        Args:
            prefix: Key prefix (e.g., "leaderboard")
            params: Parameters to include in key
            
        Returns:
            Cache key string
            
        Example:
            >>> key = self._generate_cache_key("leaderboard", {"timeframe": "7d", "limit": 100})
            >>> # Returns: "leaderboard:7d:100:abc123"
        """
        # Sort parameters for consistency
        sorted_params = sorted(params.items())
        
        # Create deterministic hash
        params_str = json.dumps(sorted_params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        
        # Build key: prefix:value1:value2:hash
        key_parts = [prefix]
        
        # Add first 2 param values for readability
        for _, value in sorted_params[:2]:
            key_parts.append(str(value))
        
        # Add hash for uniqueness
        key_parts.append(params_hash)
        
        return ":".join(key_parts)
    
    def _serialize_data(self, data: Any) -> str:
        """
        Serialize data for Redis storage (JSON).
        
        Args:
            data: Data to serialize
            
        Returns:
            JSON string
        """
        return json.dumps(data, default=str)
    
    def _deserialize_data(self, data: str) -> Any:
        """
        Deserialize data from Redis.
        
        Args:
            data: JSON string from Redis
            
        Returns:
            Deserialized data
        """
        return json.loads(data)
    
    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================
    
    async def get_cache_stats(self) -> Dict[str, int]:
        """
        Return cache statistics.
        
        Returns:
            Dictionary with hits, misses, hit rate, and cache size
            
        Example:
            >>> stats = await cache.get_cache_stats()
            >>> print(f"Hit rate: {stats['hit_rate']}%")
        """
        redis = await self._get_redis()
        
        stats = {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total_requests": self._cache_hits + self._cache_misses,
            "hit_rate": 0.0,
            "failures": self._failures,
            "redis_available": redis is not None
        }
        
        # Calculate hit rate
        if stats["total_requests"] > 0:
            stats["hit_rate"] = round(
                (self._cache_hits / stats["total_requests"]) * 100,
                2
            )
        
        # Get Redis memory info if available
        if redis:
            try:
                info = await redis.info("memory")
                stats["redis_memory_used"] = info.get("used_memory_human", "unknown")
                stats["redis_keys"] = await redis.dbsize()
            except Exception as e:
                logger.warning(f"Could not fetch Redis stats: {e}")
        
        return stats
    
    def reset_stats(self):
        """Reset cache statistics counters."""
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Cache statistics reset")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")


# ============================================================================
# Singleton Instance
# ============================================================================

# Global cache service instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """
    Get or create global cache service instance.
    
    Returns:
        CacheService singleton
    """
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
    
    return _cache_service
