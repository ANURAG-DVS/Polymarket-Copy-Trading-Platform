"""
P&L Calculation Module

Calculates profit and loss for Polymarket traders with:
- Realized P&L (closed positions)
- Unrealized P&L (open positions at current prices)
- Rolling time windows (7-day, 30-day, all-time)
- Per-market and aggregate calculations
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.api_key import Trade


class PnLCalculator:
    """
    Calculate P&L metrics for traders.
    
    Example:
        ```python
        calculator = PnLCalculator()
        
        # Calculate for a trader
        pnl_data = await calculator.calculate_trader_pnl(
            db,
            wallet_address="0x123...",
            days=7
        )
        
        print(f"7-day P&L: ${pnl_data['total_pnl']}")
        print(f"Win rate: {pnl_data['win_rate']}%")
        ```
    """
    
    def __init__(self):
        """Initialize P&L calculator"""
        logger.info("PnLCalculator initialized")
    
    async def calculate_trader_pnl(
        self,
        db: AsyncSession,
        wallet_address: str,
        days: Optional[int] = None,
        include_unrealized: bool = True
    ) -> Dict[str, any]:
        """
        Calculate comprehensive P&L for a trader.
        
        Args:
            db: Database session
            wallet_address: Trader's wallet address
            days: Time window in days (None = all-time)
            include_unrealized: Include unrealized P&L from open positions
            
        Returns:
            Dictionary with P&L metrics
        """
        # Calculate realized P&L from closed positions
        realized_pnl = await self._calculate_realized_pnl(
            db, wallet_address, days
        )
        
        # Calculate unrealized P&L from open positions
        unrealized_pnl = Decimal('0')
        if include_unrealized:
            unrealized_pnl = await self._calculate_unrealized_pnl(
                db, wallet_address
            )
        
        # Get trade statistics
        stats = await self._get_trade_stats(db, wallet_address, days)
        
        total_pnl = realized_pnl + unrealized_pnl
        
        return {
            'wallet_address': wallet_address,
            'realized_pnl': float(realized_pnl),
            'unrealized_pnl': float(unrealized_pnl),
            'total_pnl': float(total_pnl),
            'days': days,
            **stats
        }
    
    async def _calculate_realized_pnl(
        self,
        db: AsyncSession,
        wallet_address: str,
        days: Optional[int]
    ) -> Decimal:
        """
        Calculate realized P&L from closed positions.
        
        Args:
            db: Database session
            wallet_address: Trader address
            days: Time window
            
        Returns:
            Total realized P&L
        """
        query = select(func.sum(Trade.realized_pnl_usd)).where(
            and_(
                Trade.trader_wallet_address == wallet_address,
                Trade.status == 'closed',
                Trade.realized_pnl_usd.isnot(None)
            )
        )
        
        # Add time filter
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.where(Trade.exit_timestamp >= cutoff)
        
        result = await db.execute(query)
        total = result.scalar()
        
        return Decimal(str(total)) if total else Decimal('0')
    
    async def _calculate_unrealized_pnl(
        self,
        db: AsyncSession,
        wallet_address: str
    ) -> Decimal:
        """
        Calculate unrealized P&L from open positions.
        
        This requires current market prices which would be fetched
        from Polymarket API and updated periodically.
        
        Args:
            db: Database session
            wallet_address: Trader address
            
        Returns:
            Total unrealized P&L
        """
        query = select(
            func.sum(Trade.unrealized_pnl_usd)
        ).where(
            and_(
                Trade.trader_wallet_address == wallet_address,
                Trade.status == 'open',
                Trade.unrealized_pnl_usd.isnot(None)
            )
        )
        
        result = await db.execute(query)
        total = result.scalar()
        
        return Decimal(str(total)) if total else Decimal('0')
    
    async def _get_trade_stats(
        self,
        db: AsyncSession,
        wallet_address: str,
        days: Optional[int]
    ) -> Dict[str, any]:
        """
        Get trade statistics for a trader.
        
        Args:
            db: Database session
            wallet_address: Trader address
            days: Time window
            
        Returns:
            Dictionary with trade stats
        """
        # Build base query
        query = select(Trade).where(
            Trade.trader_wallet_address == wallet_address
        )
        
        # Add time filter
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.where(Trade.entry_timestamp >= cutoff)
        
        # Fetch trades
        result = await db.execute(query)
        trades = result.scalars().all()
        
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_trade_size': 0.0,
                'total_volume': 0.0
            }
        
        # Calculate stats
        total_trades = len(trades)
        closed_trades = [t for t in trades if t.status == 'closed']
        
        winning_trades = len([
            t for t in closed_trades 
            if t.realized_pnl_usd and t.realized_pnl_usd > 0
        ])
        
        losing_trades = len([
            t for t in closed_trades 
            if t.realized_pnl_usd and t.realized_pnl_usd <= 0
        ])
        
        win_rate = (winning_trades / len(closed_trades) * 100) if closed_trades else 0
        
        total_volume = sum(
            Decimal(str(t.entry_value_usd)) for t in trades
        )
        
        avg_trade_size = total_volume / len(trades) if trades else Decimal('0')
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
            'avg_trade_size': float(avg_trade_size),
            'total_volume': float(total_volume)
        }
    
    async def calculate_rolling_pnl(
        self,
        db: AsyncSession,
        wallet_address: str
    ) -> Dict[str, Decimal]:
        """
        Calculate P&L for multiple time windows.
        
        Args:
            db: Database session
            wallet_address: Trader address
            
        Returns:
            Dictionary with P&L for different windows
        """
        # Calculate for different time windows
        pnl_7d = await self.calculate_trader_pnl(db, wallet_address, days=7)
        pnl_30d = await self.calculate_trader_pnl(db, wallet_address, days=30)
        pnl_all_time = await self.calculate_trader_pnl(db, wallet_address, days=None)
        
        return {
            'pnl_7d': Decimal(str(pnl_7d['total_pnl'])),
            'pnl_30d': Decimal(str(pnl_30d['total_pnl'])),
            'pnl_all_time': Decimal(str(pnl_all_time['total_pnl'])),
            
            'win_rate_7d': pnl_7d['win_rate'],
            'win_rate_30d': pnl_30d['win_rate'],
            'win_rate_all_time': pnl_all_time['win_rate'],
            
            'total_trades_7d': pnl_7d['total_trades'],
            'total_trades_30d': pnl_30d['total_trades'],
            'total_trades_all_time': pnl_all_time['total_trades'],
        }
    
    async def calculate_sharpe_ratio(
        self,
        db: AsyncSession,
        wallet_address: str,
        days: int = 30,
        risk_free_rate: Decimal = Decimal('0.05')
    ) -> Optional[Decimal]:
        """
        Calculate Sharpe ratio for a trader.
        
        Sharpe Ratio = (Average Return - Risk Free Rate) / Std Dev of Returns
        
        Args:
            db: Database session
            wallet_address: Trader address
            days: Time window
            risk_free_rate: Annual risk-free rate (default: 5%)
            
        Returns:
            Sharpe ratio or None if insufficient data
        """
        # Fetch closed trades
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = select(Trade).where(
            and_(
                Trade.trader_wallet_address == wallet_address,
                Trade.status == 'closed',
                Trade.exit_timestamp >= cutoff,
                Trade.realized_pnl_percent.isnot(None)
            )
        )
        
        result = await db.execute(query)
        trades = result.scalars().all()
        
        if len(trades) < 2:
            return None
        
        # Calculate returns
        returns = [Decimal(str(t.realized_pnl_percent)) for t in trades]
        
        # Calculate average return
        avg_return = sum(returns) / len(returns)
        
        # Calculate standard deviation
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** Decimal('0.5')
        
        if std_dev == 0:
            return None
        
        # Annualize risk-free rate to match period
        period_risk_free = risk_free_rate * (Decimal(days) / Decimal('365'))
        
        # Calculate Sharpe ratio
        sharpe = (avg_return - period_risk_free) / std_dev
        
        return sharpe


# Singleton instance
_pnl_calculator: Optional[PnLCalculator] = None


def get_pnl_calculator() -> PnLCalculator:
    """Get singleton instance of PnLCalculator"""
    global _pnl_calculator
    if _pnl_calculator is None:
        _pnl_calculator = PnLCalculator()
    return _pnl_calculator
