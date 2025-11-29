from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from app.models.user import User
from app.models.trade import Trade, TradeStatus
from app.models.copy_relationship import CopyRelationship, RelationshipStatus
from app.models.trader import Trader
from app.models.notification import Notification, UserBalance
from app.schemas.dashboard import (
    DashboardOverview,
    PLChartData,
    PLChartResponse,
    RecentTrade,
    NotificationResponse
)
import logging

logger = logging.getLogger(__name__)

class DashboardService:
    """Service for dashboard data aggregation"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_overview(self, user_id: int) -> DashboardOverview:
        """Get dashboard overview data"""
        
        # Get user's trades for P&L calculation
        trades_result = await self.db.execute(
            select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.status == TradeStatus.OPEN
                )
            )
        )
        open_trades = trades_result.scalars().all()
        
        # Calculate total unrealized P&L
        total_pnl = sum(trade.unrealized_pnl for trade in open_trades)
        
        # Get P&L from 7 days ago for change calculation
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        pnl_7d_ago_result = await self.db.execute(
            select(func.sum(Trade.realized_pnl))
            .where(
                and_(
                    Trade.user_id == user_id,
                    Trade.closed_at <= seven_days_ago
                )
            )
        )
        pnl_7d_ago = pnl_7d_ago_result.scalar() or 0
        
        # Calculate 7-day change percentage
        if pnl_7d_ago != 0:
            pnl_7d_change = ((total_pnl - pnl_7d_ago) / abs(pnl_7d_ago)) * 100
        else:
            pnl_7d_change = 0 if total_pnl == 0 else 100
        
        # Get sparkline data (last 7 days daily P&L)
        sparkline = await self._get_pnl_sparkline(user_id, 7)
        
        # Get active copy relationships
        active_copies_result = await self.db.execute(
            select(CopyRelationship, Trader)
            .join(Trader, CopyRelationship.trader_id == Trader.id)
            .where(
                and_(
                    CopyRelationship.user_id == user_id,
                    CopyRelationship.status == RelationshipStatus.ACTIVE
                )
            )
        )
        active_copies = active_copies_result.all()
        
        active_traders = [
            {
                "id": trader.id,
                "wallet_address": trader.wallet_address,
                "avatar": None  # Can add avatar URL if available
            }
            for _, trader in active_copies
        ]
        
        # Get user balance
        balance_result = await self.db.execute(
            select(UserBalance).where(UserBalance.user_id == user_id)
        )
        balance = balance_result.scalars().first()
        
        available_balance = balance.available_balance if balance else 0
        locked_balance = balance.locked_balance if balance else 0
        
        # Calculate open positions value
        open_positions_value = sum(trade.amount_usd for trade in open_trades)
        
        return DashboardOverview(
            total_pnl=total_pnl,
            pnl_7d_change=pnl_7d_change,
            pnl_sparkline=sparkline,
            active_copies=len(active_copies),
            active_traders=active_traders[:5],  # Show max 5
            open_positions=len(open_trades),
            open_positions_value=open_positions_value,
            available_balance=available_balance,
            locked_balance=locked_balance
        )
    
    async def get_pnl_chart_data(
        self,
        user_id: int,
        period: str = "7d",
        group_by: Optional[str] = None
    ) -> PLChartResponse:
        """Get P&L chart data"""
        
        # Determine date range
        if period == "24h":
            days = 1
        elif period == "7d":
            days = 7
        elif period == "30d":
            days = 30
        else:  # all
            days = 365  # Or fetch from first trade
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        if group_by == "market":
            # Group by market
            query = select(
                func.date(Trade.created_at).label('date'),
                Trade.market_title.label('label'),
                func.sum(Trade.realized_pnl + Trade.unrealized_pnl).label('pnl')
            ).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.created_at >= start_date
                )
            ).group_by(
                func.date(Trade.created_at),
                Trade.market_title
            ).order_by(
                func.date(Trade.created_at)
            )
        elif group_by == "trader":
            # Group by trader
            query = select(
                func.date(Trade.created_at).label('date'),
                Trader.wallet_address.label('label'),
                func.sum(Trade.realized_pnl + Trade.unrealized_pnl).label('pnl')
            ).join(
                Trader, Trade.trader_id == Trader.id
            ).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.created_at >= start_date
                )
            ).group_by(
                func.date(Trade.created_at),
                Trader.wallet_address
            ).order_by(
                func.date(Trade.created_at)
            )
        else:
            # No grouping, just daily totals
            query = select(
                func.date(Trade.created_at).label('date'),
                func.sum(Trade.realized_pnl + Trade.unrealized_pnl).label('pnl')
            ).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.created_at >= start_date
                )
            ).group_by(
                func.date(Trade.created_at)
            ).order_by(
                func.date(Trade.created_at)
            )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        # Calculate cumulative P&L
        cumulative_pnl = 0
        chart_data = []
        
        for row in rows:
            cumulative_pnl += row.pnl
            chart_data.append(PLChartData(
                date=row.date.isoformat(),
                pnl=cumulative_pnl,
                label=row.label if group_by else None
            ))
        
        return PLChartResponse(
            data=chart_data,
            total_pnl=cumulative_pnl,
            period=period
        )
    
    async def get_recent_trades(self, user_id: int, limit: int = 10) -> List[RecentTrade]:
        """Get recent trades for dashboard"""
        result = await self.db.execute(
            select(Trade)
            .where(Trade.user_id == user_id)
            .order_by(desc(Trade.created_at))
            .limit(limit)
        )
        trades = result.scalars().all()
        
        return [RecentTrade.from_orm(trade) for trade in trades]
    
    async def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 10
    ) -> List[NotificationResponse]:
        """Get user notifications"""
        query = select(Notification).where(
            Notification.user_id == user_id
        )
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        query = query.order_by(desc(Notification.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        return [NotificationResponse.from_orm(n) for n in notifications]
    
    async def mark_notification_read(self, notification_id: int, user_id: int) -> bool:
        """Mark a notification as read"""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
        )
        notification = result.scalars().first()
        
        if not notification:
            return False
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        await self.db.commit()
        
        return True
    
    async def _get_pnl_sparkline(self, user_id: int, days: int) -> List[float]:
        """Get sparkline data for last N days"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.date(Trade.created_at).label('date'),
            func.sum(Trade.realized_pnl + Trade.unrealized_pnl).label('daily_pnl')
        ).where(
            and_(
                Trade.user_id == user_id,
                Trade.created_at >= start_date
            )
        ).group_by(
            func.date(Trade.created_at)
        ).order_by(
            func.date(Trade.created_at)
        )
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        # Fill in missing days with 0
        sparkline = []
        current_date = start_date.date()
        end_date = datetime.utcnow().date()
        
        data_dict = {row.date: row.daily_pnl for row in rows}
        
        cumulative = 0
        while current_date <= end_date:
            daily_pnl = data_dict.get(current_date, 0)
            cumulative += daily_pnl
            sparkline.append(cumulative)
            current_date += timedelta(days=1)
        
        return sparkline[-days:] if len(sparkline) > days else sparkline
