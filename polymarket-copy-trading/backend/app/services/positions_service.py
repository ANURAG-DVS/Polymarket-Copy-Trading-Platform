from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.models.trade import Trade, TradeStatus
from app.models.trader import Trader
from app.schemas.positions import PositionFilters, OpenPositionResponse, ClosedPositionResponse
import logging

logger = logging.getLogger(__name__)

class PositionsService:
    """Service for positions management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_open_positions(
        self,
        user_id: int,
        filters: PositionFilters
    ) -> Tuple[List[Trade], int]:
        """Get user's open positions with filters"""
        
        query = select(Trade).where(
            and_(
                Trade.user_id == user_id,
                Trade.status == TradeStatus.OPEN
            )
        )
        
        # Apply filters
        if filters.trader_id:
            query = query.where(Trade.trader_id == filters.trader_id)
        
        if filters.start_date:
            query = query.where(Trade.created_at >= filters.start_date)
        
        if filters.end_date:
            query = query.where(Trade.created_at <= filters.end_date)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (filters.page - 1) * filters.limit
        query = query.order_by(desc(Trade.created_at)).offset(offset).limit(filters.limit)
        
        result = await self.db.execute(query)
        positions = result.scalars().all()
        
        return positions, total
    
    async def get_closed_positions(
        self,
        user_id: int,
        filters: PositionFilters
    ) -> Tuple[List[Trade], int]:
        """Get user's closed positions with filters"""
        
        query = select(Trade).where(
            and_(
                Trade.user_id == user_id,
                Trade.status == TradeStatus.CLOSED
            )
        )
        
        # Apply filters
        if filters.trader_id:
            query = query.where(Trade.trader_id == filters.trader_id)
        
        if filters.start_date:
            query = query.where(Trade.closed_at >= filters.start_date)
        
        if filters.end_date:
            query = query.where(Trade.closed_at <= filters.end_date)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (filters.page - 1) * filters.limit
        query = query.order_by(desc(Trade.closed_at)).offset(offset).limit(filters.limit)
        
        result = await self.db.execute(query)
        positions = result.scalars().all()
        
        return positions, total
    
    async def close_position(self, position_id: int, user_id: int) -> Trade:
        """Manually close a position"""
        
        result = await self.db.execute(
            select(Trade).where(
                and_(
                    Trade.id == position_id,
                    Trade.user_id == user_id,
                    Trade.status == TradeStatus.OPEN
                )
            )
        )
        position = result.scalars().first()
        
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Position not found or already closed"
            )
        
        # Update position
        position.status = TradeStatus.CLOSED
        position.closed_at = datetime.utcnow()
        position.exit_price = position.current_price
        position.realized_pnl = position.unrealized_pnl
        position.unrealized_pnl = 0
        
        await self.db.commit()
        await self.db.refresh(position)
        
        logger.info(f"Manually closed position {position_id} for user {user_id}")
        return position
    
    async def get_position_details(self, position_id: int, user_id: int) -> dict:
        """Get detailed position information with timeline"""
        
        result = await self.db.execute(
            select(Trade).where(
                and_(
                    Trade.id == position_id,
                    Trade.user_id == user_id
                )
            )
        )
        position = result.scalars().first()
        
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Position not found"
            )
        
        # Build timeline (simplified - in production, track actual events)
        timeline = [
            {
                "event": "Position Opened",
                "timestamp": position.created_at.isoformat(),
                "details": f"Bought {position.quantity} shares at ${position.entry_price}"
            }
        ]
        
        if position.status == TradeStatus.CLOSED:
            timeline.append({
                "event": "Position Closed",
                "timestamp": position.closed_at.isoformat(),
                "details": f"Sold at ${position.exit_price}, P&L: ${position.realized_pnl:.2f}"
            })
        
        return {
            "position": position,
            "timeline": timeline
        }
