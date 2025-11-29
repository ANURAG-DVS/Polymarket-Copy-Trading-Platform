from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.models.trader import Trader
from app.models.trade import Trade
from app.schemas.trader import TraderFilters
import logging

logger = logging.getLogger(__name__)

class TraderService:
    """Service for trader operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_leaderboard(
        self,
        filters: TraderFilters
    ) -> tuple[List[Trader], int]:
        """Get traders leaderboard with filters and pagination"""
        
        # Build query
        query = select(Trader).where(Trader.is_active == True)
        
        # Apply filters
        if filters.min_pnl is not None:
            if filters.timeframe == "7d":
                query = query.where(Trader.pnl_7d >= filters.min_pnl)
            elif filters.timeframe == "30d":
                query = query.where(Trader.pnl_30d >= filters.min_pnl)
            else:
                query = query.where(Trader.pnl_all_time >= filters.min_pnl)
        
        if filters.min_win_rate is not None:
            query = query.where(Trader.win_rate >= filters.min_win_rate)
        
        if filters.min_trades is not None:
            query = query.where(Trader.total_trades >= filters.min_trades)
        
        if filters.search:
            query = query.where(
                Trader.wallet_address.ilike(f"%{filters.search}%")
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply sorting
        sort_column = getattr(Trader, filters.sort_by, Trader.rank)
        if filters.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (filters.page - 1) * filters.limit
        query = query.offset(offset).limit(filters.limit)
        
        # Execute query
        result = await self.db.execute(query)
        traders = result.scalars().all()
        
        logger.info(f"Retrieved {len(traders)} traders (total: {total})")
        return traders, total
    
    async def get_trader_by_id(self, trader_id: int) -> Optional[Trader]:
        """Get trader by ID"""
        result = await self.db.execute(
            select(Trader).where(Trader.id == trader_id)
        )
        return result.scalars().first()
    
    async def get_trader_by_address(self, wallet_address: str) -> Optional[Trader]:
        """Get trader by wallet address"""
        result = await self.db.execute(
            select(Trader).where(Trader.wallet_address == wallet_address)
        )
        return result.scalars().first()
    
    async def get_trader_trades(
        self,
        trader_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Trade]:
        """Get trader's recent trades"""
        result = await self.db.execute(
            select(Trade)
            .where(Trade.trader_id == trader_id)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def get_trader_pnl_history(
        self,
        trader_id: int,
        days: int = 30
    ) -> List[dict]:
        """Get trader's P&L history over time"""
        # This would aggregate daily P&L
        # For now, returning placeholder
        # In production, you'd calculate daily cumulative P&L
        
        query = select(
            func.date(Trade.created_at).label('date'),
            func.sum(Trade.realized_pnl).label('daily_pnl')
        ).where(
            and_(
                Trade.trader_id == trader_id,
                Trade.created_at >= func.now() - func.make_interval(days=days)
            )
        ).group_by(
            func.date(Trade.created_at)
        ).order_by(
            func.date(Trade.created_at)
        )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        cumulative_pnl = 0
        history = []
        for row in rows:
            cumulative_pnl += row.daily_pnl
            history.append({
                "date": row.date.isoformat(),
                "pnl": cumulative_pnl
            })
        
        return history
