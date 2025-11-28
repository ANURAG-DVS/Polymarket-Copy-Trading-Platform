"""
Rate Limiting Service

Prevents abuse by limiting the rate of sensitive operations like decryption.
Uses Redis for distributed rate limiting.
"""

from typing import Optional
from datetime import datetime
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded"""
    pass


class RateLimitService:
    """
    Provides distributed rate limiting using Redis.
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        logger.info("RateLimitService initialized")
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
        return self.redis_client
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> None:
        """
        Check if rate limit is exceeded using sliding window.
        
        Args:
            key: Unique key for this rate limit (e.g., "decrypt:user:123")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Raises:
            RateLimitExceeded: If limit is exceeded
        """
        r = await self._get_redis()
        
        # Use sorted set for sliding window
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        rate_limit_key = f"rate_limit:{key}"
        
        # Remove old entries
        await r.zremrangebyscore(rate_limit_key, 0, window_start)
        
        # Count current requests
        count = await r.zcard(rate_limit_key)
        
        if count >= max_requests:
            raise RateLimitExceeded(
                f"Rate limit exceeded for {key}: {count}/{max_requests} in {window_seconds}s"
            )
        
        # Add current request
        await r.zadd(rate_limit_key, {str(now): now})
        
        # Set expiration
        await r.expire(rate_limit_key, window_seconds)
        
        logger.debug(f"Rate limit check passed: {key} ({count + 1}/{max_requests})")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()


# Singleton instance
_rate_limit_service: Optional[RateLimitService] = None


def get_rate_limit_service() -> RateLimitService:
    """Get singleton instance of RateLimitService"""
    global _rate_limit_service
    if _rate_limit_service is None:
        _rate_limit_service = RateLimitService()
    return _rate_limit_service
