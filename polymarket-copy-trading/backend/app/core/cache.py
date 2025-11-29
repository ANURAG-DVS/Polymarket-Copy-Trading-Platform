from typing import Optional, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
import json
import hashlib
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class CacheMiddleware(BaseHTTPMiddleware):
    """Redis caching middleware for API responses"""
    
    def __init__(self, app, redis_url: str = None):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = None
    
    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)
        
        # Skip caching for certain paths
        skip_paths = ["/health", "/metrics", "/docs", "/openapi.json"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Try to get from cache
        try:
            if not self.redis_client:
                self.redis_client = await redis.from_url(self.redis_url)
            
            cached_response = await self.redis_client.get(cache_key)
            
            if cached_response:
                logger.debug(f"Cache HIT: {cache_key}")
                data = json.loads(cached_response)
                return Response(
                    content=data['content'],
                    status_code=data['status_code'],
                    headers=dict(data['headers']),
                    media_type=data['media_type']
                )
            
            logger.debug(f"Cache MISS: {cache_key}")
        except Exception as e:
            logger.error(f"Cache read error: {e}")
        
        # Process request
        response = await call_next(request)
        
        # Cache successful responses
        if response.status_code == 200:
            try:
                # Get TTL based on endpoint
                ttl = self._get_ttl(request.url.path)
                
                if ttl > 0:
                    # Read response body
                    body = b""
                    async for chunk in response.body_iterator:
                        body += chunk
                    
                    # Cache the response
                    cache_data = {
                        'content': body.decode(),
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'media_type': response.media_type
                    }
                    
                    await self.redis_client.setex(
                        cache_key,
                        ttl,
                        json.dumps(cache_data)
                    )
                    
                    # Return new response with cached body
                    return Response(
                        content=body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
            except Exception as e:
                logger.error(f"Cache write error: {e}")
        
        return response
    
    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key from request"""
        # Include path, query params, and auth header for personalized caching
        key_parts = [
            request.url.path,
            str(sorted(request.query_params.items())),
            request.headers.get('Authorization', '')
        ]
        
        key_string = '|'.join(key_parts)
        return f"api_cache:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def _get_ttl(self, path: str) -> int:
        """Get cache TTL based on endpoint"""
        ttl_map = {
            '/api/v1/traders/leaderboard': 60,  # 1 minute
            '/api/v1/traders/': 300,  # 5 minutes (trader details)
            '/api/v1/dashboard': 30,  # 30 seconds
            '/api/v1/markets': 30,  # 30 seconds (market data)
        }
        
        for prefix, ttl in ttl_map.items():
            if path.startswith(prefix):
                return ttl
        
        return 0  # No caching by default

# Decorator for function-level caching
def cache_result(ttl: int = 60, key_prefix: str = "fn"):
    """Decorator to cache function results in Redis"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__, str(args), str(sorted(kwargs.items()))]
            cache_key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            try:
                r = await redis.from_url(settings.REDIS_URL)
                cached = await r.get(f"fn_cache:{cache_key}")
                
                if cached:
                    logger.debug(f"Function cache HIT: {func.__name__}")
                    return json.loads(cached)
                
                logger.debug(f"Function cache MISS: {func.__name__}")
            except Exception as e:
                logger.error(f"Cache read error: {e}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            try:
                r = await redis.from_url(settings.REDIS_URL)
                await r.setex(
                    f"fn_cache:{cache_key}",
                    ttl,
                    json.dumps(result)
                )
            except Exception as e:
                logger.error(f"Cache write error: {e}")
            
            return result
        
        return wrapper
    return decorator

# Usage:
# @cache_result(ttl=60, key_prefix="traders")
# async def get_leaderboard(filters):
#     ...
