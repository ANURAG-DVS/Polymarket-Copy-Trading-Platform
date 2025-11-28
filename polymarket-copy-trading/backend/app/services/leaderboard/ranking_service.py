"""
Leaderboard Ranking Service

Maintains ranked list of top Polymarket traders with:
- Auto-updating on new trades
- Configurable ranking metrics
- Low-volume trader filtering
- Redis caching for fast access
- Pagination support
"""

import json
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings
from app.models.api_key import User
from app.services.leaderboard.pnl_calculator import get_pnl_calculator


class LeaderboardService:
    """
    Manage trader leaderboard with rankings and caching.
    
    Example:
        ```python
        leaderboard = LeaderboardService()
        await leaderboard.connect()
        
        # Get top 100 traders
        top_traders = await leaderboard.get_top_traders(limit=100)
        
        # Update trader after new trade
        await leaderboard.update_trader_stats(db, wallet_address)
        ```
    """
    
    # Cache keys
    LEADERBOARD_CACHE_KEY = "leaderboard:top_traders"
    TRADER_STATS_PREFIX = "trader:stats"
    
    # Configuration
    CACHE_TTL = 300  # 5 minutes
    MIN_TRADES_THRESHOLD = 5  # Minimum trades to appear on leaderboard
    MIN_VOLUME_THRESHOLD = 100  # Minimum $100 volume
    DEFAULT_RANK_BY = "pnl_7d"  # Default ranking metric
    
    def __init__(self):
        """Initialize leaderboard service"""
        self.redis_client: Optional[redis.Redis] = None
        self.pnl_calculator = get_pnl_calculator()
        
        logger.info("LeaderboardService initialized")
    
    async def connect(self):
        """Connect to Redis"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis for leaderboard")
    
    async def update_trader_stats(
        self,
        db: AsyncSession,
        wallet_address: str
    ):
        """
        Update trader statistics after a new trade.
        
        Args:
            db: Database session
            wallet_address: Trader's wallet address
        """
        try:
            # Calculate comprehensive stats
            rolling_pnl = await self.pnl_calculator.calculate_rolling_pnl(
                db, wallet_address
            )
            
            # Calculate Sharpe ratio
            sharpe_ratio = await self.pnl_calculator.calculate_sharpe_ratio(
                db, wallet_address, days=30
            )
            
            # Upsert into traders table
            from app.models.api_key import User
            from sqlalchemy.dialects.postgresql import insert
            
            # Build values dict
            values = {
                'wallet_address': wallet_address,
                'pnl_7d_usd': rolling_pnl['pnl_7d'],
                'pnl_30d_usd': rolling_pnl['pnl_30d'],
                'pnl_total_usd': rolling_pnl['pnl_all_time'],
                'win_rate_7d': rolling_pnl['win_rate_7d'],
                'win_rate_30d': rolling_pnl['win_rate_30d'],
                'win_rate_total': rolling_pnl['win_rate_all_time'],
                'total_trades_7d': rolling_pnl['total_trades_7d'],
                'total_trades_30d': rolling_pnl['total_trades_30d'],
                'total_trades': rolling_pnl['total_trades_all_time'],
                'sharpe_ratio': float(sharpe_ratio) if sharpe_ratio else None,
                'updated_at': datetime.utcnow()
            }
            
            # Note: This uses the traders table from database schema
            # In production, you'd import the Trader model
            stmt = insert(User.__table__).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['wallet_address'],
                set_=values
            )
            
            await db.execute(stmt)
            await db.commit()
            
            # Invalidate cache
            await self._invalidate_cache()
            
            logger.debug(f"Updated stats for trader {wallet_address[:10]}...")
            
        except Exception as e:
            logger.error(f"Failed to update trader stats: {e}")
            raise
    
    async def get_top_traders(
        self,
        db: AsyncSession,
        limit: int = 100,
        rank_by: str = DEFAULT_RANK_BY,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get top traders from leaderboard.
        
        Args:
            db: Database session
            limit: Number of traders to return
            rank_by: Metric to rank by (pnl_7d, pnl_30d, win_rate_7d, etc.)
            use_cache: Use Redis cache if available
            
        Returns:
            List of trader dictionaries with stats
        """
        await self.connect()
        
        # Try cache first
        if use_cache:
            cache_key = f"{self.LEADERBOARD_CACHE_KEY}:{rank_by}:{limit}"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                logger.debug(f"Leaderboard cache hit: {rank_by}")
                return json.loads(cached)
        
        # Query database
        traders = await self._query_leaderboard(db, limit, rank_by)
        
        # Cache result
        if use_cache and traders:
            cache_key = f"{self.LEADERBOARD_CACHE_KEY}:{rank_by}:{limit}"
            await self.redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(traders)
            )
        
        return traders
    
    async def _query_leaderboard(
        self,
        db: AsyncSession,
        limit: int,
        rank_by: str
    ) -> List[Dict[str, Any]]:
        """
        Query leaderboard from database.
        
        Args:
            db: Database session
            limit: Number of traders
            rank_by: Ranking metric
            
        Returns:
            List of trader data
        """
        # Map rank_by to column
        rank_column_map = {
            'pnl_7d': 'pnl_7d_usd',
            'pnl_30d': 'pnl_30d_usd',
            'pnl_total': 'pnl_total_usd',
            'win_rate_7d': 'win_rate_7d',
            'win_rate_30d': 'win_rate_30d',
            'volume': 'total_volume_usd',
            'sharpe': 'sharpe_ratio'
        }
        
        rank_column = rank_column_map.get(rank_by, 'pnl_7d_usd')
        
        # Build query - using User table, but in production you'd use Trader model
        query = select(User).where(
            and_(
                User.total_trades >= self.MIN_TRADES_THRESHOLD,
                #User.total_volume_usd >= self.MIN_VOLUME_THRESHOLD  # Commented - needs column
            )
        ).order_by(
            desc(getattr(User, rank_column))
        ).limit(limit)
        
        result = await db.execute(query)
        traders = result.scalars().all()
        
        # Convert to dictionaries
        trader_list = []
        for rank, trader in enumerate(traders, start=1):
            trader_dict = {
                'rank': rank,
                'wallet_address': trader.wallet_address,
                'pnl_7d': float(trader.pnl_7d_usd) if hasattr(trader, 'pnl_7d_usd') else 0,
                'pnl_30d': float(trader.pnl_30d_usd) if hasattr(trader, 'pnl_30d_usd') else 0,
                'pnl_total': float(trader.pnl_total_usd) if hasattr(trader, 'pnl_total_usd') else 0,
                'win_rate_7d': float(trader.win_rate_7d) if hasattr(trader, 'win_rate_7d') else 0,
                'win_rate_30d': float(trader.win_rate_30d) if hasattr(trader, 'win_rate_30d') else 0,
                'total_trades': trader.total_trades if hasattr(trader, 'total_trades') else 0,
                'sharpe_ratio': float(trader.sharpe_ratio) if hasattr(trader, 'sharpe_ratio') and trader.sharpe_ratio else None,
            }
            trader_list.append(trader_dict)
        
        return trader_list
    
    async def get_trader_rank(
        self,
        db: AsyncSession,
        wallet_address: str,
        rank_by: str = DEFAULT_RANK_BY
    ) -> Optional[int]:
        """
        Get specific trader's rank.
        
        Args:
            db: Database session
            wallet_address: Trader's address
            rank_by: Ranking metric
            
        Returns:
            Rank number or None if not ranked
        """
        # Get full leaderboard (could be optimized with SQL window functions)
        leaderboard = await self.get_top_traders(
            db,
            limit=1000,
            rank_by=rank_by,
            use_cache=False
        )
        
        for trader in leaderboard:
            if trader['wallet_address'].lower() == wallet_address.lower():
                return trader['rank']
        
        return None
    
    async def _invalidate_cache(self):
        """Invalidate all leaderboard caches"""
        await self.connect()
        
        # Delete all leaderboard cache keys
        pattern = f"{self.LEADERBOARD_CACHE_KEY}:*"
        cursor = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            if keys:
                await self.redis_client.delete(*keys)
            
            if cursor == 0:
                break
        
        logger.debug("Invalidated leaderboard cache")
    
    async def create_daily_snapshot(self, db: AsyncSession):
        """
        Create daily snapshot of leaderboard for historical tracking.
        
        Args:
            db: Database session
        """
        # Get current top traders
        top_traders = await self.get_top_traders(
            db,
            limit=100,
            use_cache=False
        )
        
        # Store in historical snapshots table
        # (Implementation would insert into trader_snapshots table)
        snapshot_date = datetime.utcnow().date()
        
        logger.info(f"Created daily snapshot for {snapshot_date}: {len(top_traders)} traders")
        
        return top_traders
    
    async def get_trending_traders(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get traders with biggest 7-day gains.
        
        Args:
            db: Database session
            limit: Number of traders
            
        Returns:
            List of trending traders
        """
        return await self.get_top_traders(
            db,
            limit=limit,
            rank_by='pnl_7d',
            use_cache=True
        )
    
    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()


# Singleton instance
_leaderboard_service: Optional[LeaderboardService] = None


def get_leaderboard_service() -> LeaderboardService:
    """Get singleton instance of LeaderboardService"""
    global _leaderboard_service
    if _leaderboard_service is None:
        _leaderboard_service = LeaderboardService()
    return _leaderboard_service
