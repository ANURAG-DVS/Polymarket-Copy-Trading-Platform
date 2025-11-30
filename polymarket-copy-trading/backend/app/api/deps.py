from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis
import hashlib
import json

from app.db.session import async_session
from app.models.user import User
from app.core.security import verify_token
from app.core.config import settings

security = HTTPBearer()

async def get_db() -> Generator:
    """Get database session"""
    async with async_session() as session:
        yield session

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    
    payload = verify_token(token, settings.JWT_SECRET)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


# ============================================================================
# Redis Dependencies
# ============================================================================

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get Redis connection with connection pooling."""
    global _redis_pool
    
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10
        )
    
    return _redis_pool


async def close_redis():
    """Close Redis connection pool on shutdown."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()


# ============================================================================
# Cache Utilities
# ============================================================================

def get_cache_key(prefix: str, **params) -> str:
    """Generate deterministic cache key from parameters."""
    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
    
    if params:
        primary_values = [str(v) for k, v in sorted_params[:2]]
        key_parts = [prefix] + primary_values + [params_hash]
    else:
        key_parts = [prefix, params_hash]
    
    return ":".join(key_parts)


async def get_cached_data(cache: aioredis.Redis, key: str, default=None):
    """Get data from cache with JSON deserialization."""
    try:
        cached = await cache.get(key)
        if cached:
            return json.loads(cached)
        return default
    except Exception:
        return default


async def set_cached_data(cache: aioredis.Redis, key: str, data, ttl: int = 60) -> bool:
    """Set data in cache with JSON serialization."""
    try:
        serialized = json.dumps(data, default=str)
        await cache.setex(key, ttl, serialized)
        return True
    except Exception:
        return False
