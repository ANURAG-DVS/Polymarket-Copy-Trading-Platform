"""
Database session management with proper configuration to prevent recursion issues.

CRITICAL: expire_on_commit=False prevents detached instance errors and lazy loading issues.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Configure async engine with proper pool settings
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
    # Use NullPool for Celery workers to avoid connection issues
    poolclass=NullPool if settings.ENVIRONMENT == "worker" else None,
)

# Async session factory with expire_on_commit=False
# CRITICAL: Prevents detached instance errors and relationship loading issues
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # CRITICAL: Prevents lazy loading after commit
    autocommit=False,
    autoflush=False
)


async def get_db():
    """
    Dependency for FastAPI endpoints.
    Yields async database session and ensures cleanup.
    
    Usage in endpoint:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
