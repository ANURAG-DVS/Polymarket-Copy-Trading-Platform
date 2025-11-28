"""
Risk Management & Circuit Breaker Service

Emergency controls and risk management safeguards.
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import redis.asyncio as redis

from app.models.api_key import Trade, User
from app.core.config import settings


class CircuitBreakerReason(str, Enum):
    """Circuit breaker trigger reasons"""
    HIGH_FAILURE_RATE = "high_failure_rate"
    BLOCKCHAIN_RPC_DOWN = "blockchain_rpc_down"
    API_ERROR_RATE = "api_error_rate"
    MANUAL_TRIGGER = "manual_trigger"
    SUSPICIOUS_TRADER = "suspicious_trader"


@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status"""
    is_active: bool
    reason: Optional[CircuitBreakerReason]
    triggered_at: Optional[datetime]
    triggered_by: Optional[str]  # user_id or 'system'
    can_resume: bool
    backlog_count: int


class RiskManagementService:
    """
    Risk management and circuit breaker controls.
    
    Features:
    - Automatic circuit breakers
    - Per-user risk limits
    - Trader watchdog
    - Manual overrides
    """
    
    # Circuit breaker thresholds
    FAILURE_RATE_THRESHOLD = 0.50  # 50%
    API_ERROR_RATE_THRESHOLD = 0.30  # 30%
    RPC_DOWN_TIMEOUT_MINUTES = 5
    
    # Per-user risk limits
    DEFAULT_DAILY_LOSS_LIMIT_USD = Decimal('1000')
    DEFAULT_DAILY_LOSS_PERCENT = Decimal('20')  # 20% of portfolio
    COOLING_PERIOD_HOURS = 24
    
    # Trader watchdog thresholds
    TRADE_SIZE_SPIKE_MULTIPLIER = 10
    SINGLE_DAY_LOSS_THRESHOLD = Decimal('0.50')  # 50%
    
    def __init__(self):
        """Initialize risk management service"""
        self.redis_url = settings.REDIS_URL
        self.redis: Optional[redis.Redis] = None
        
        # Circuit breaker key
        self.circuit_breaker_key = "circuit_breaker:status"
        self.paused_traders_key = "circuit_breaker:paused_traders"
        
        logger.info("RiskManagementService initialized")
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = await redis.from_url(self.redis_url)
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
    
    # =========================================================================
    # Circuit Breaker
    # =========================================================================
    
    async def check_failure_rate(
        self,
        db: AsyncSession
    ) -> tuple[bool, float]:
        """
        Check if trade failure rate exceeds threshold.
        
        Returns:
            (should_trigger, failure_rate)
        """
        # Get trades from last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        # Total trades
        query_total = select(func.count()).where(
            Trade.entry_timestamp >= one_hour_ago
        )
        result_total = await db.execute(query_total)
        total_trades = result_total.scalar() or 0
        
        if total_trades == 0:
            return False, 0.0
        
        # Failed trades
        query_failed = select(func.count()).where(
            and_(
                Trade.entry_timestamp >= one_hour_ago,
                Trade.status.in_(['failed', 'permanently_failed'])
            )
        )
        result_failed = await db.execute(query_failed)
        failed_trades = result_failed.scalar() or 0
        
        failure_rate = failed_trades / total_trades
        
        should_trigger = failure_rate > self.FAILURE_RATE_THRESHOLD
        
        if should_trigger:
            logger.error(
                f"High failure rate detected: {failure_rate * 100:.1f}% "
                f"({failed_trades}/{total_trades})"
            )
        
        return should_trigger, failure_rate
    
    async def check_blockchain_rpc(self) -> tuple[bool, Optional[str]]:
        """
        Check if blockchain RPC is down.
        
        Returns:
            (is_down, error_message)
        """
        try:
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
            
            # Try to get latest block
            block = w3.eth.block_number
            
            return False, None
            
        except Exception as e:
            return True, str(e)
    
    async def trigger_circuit_breaker(
        self,
        reason: CircuitBreakerReason,
        triggered_by: str = "system",
        details: Optional[str] = None
    ):
        """
        Trigger circuit breaker to pause all copy trading.
        
        Args:
            reason: Reason for trigger
            triggered_by: Who triggered (user_id or 'system')
            details: Additional details
        """
        if not self.redis:
            await self.connect()
        
        status = {
            "is_active": True,
            "reason": reason.value,
            "triggered_at": datetime.utcnow().isoformat(),
            "triggered_by": triggered_by,
            "details": details
        }
        
        # Store in Redis
        await self.redis.set(
            self.circuit_breaker_key,
            str(status)
        )
        
        logger.critical(
            f"🚨 CIRCUIT BREAKER TRIGGERED: {reason.value} by {triggered_by}. "
            f"Details: {details}"
        )
        
        # TODO: Send alerts to admins
        # TODO: Send notifications to all users
    
    async def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is active"""
        if not self.redis:
            await self.connect()
        
        status = await self.redis.get(self.circuit_breaker_key)
        
        if status:
            import ast
            status_dict = ast.literal_eval(status.decode())
            return status_dict.get('is_active', False)
        
        return False
    
    async def reset_circuit_breaker(
        self,
        reset_by: str
    ):
        """
        Reset circuit breaker to resume operations.
        
        Args:
            reset_by: Admin user ID
        """
        if not self.redis:
            await self.connect()
        
        await self.redis.delete(self.circuit_breaker_key)
        
        logger.info(f"✅ Circuit breaker reset by {reset_by}")
        
        # TODO: Send notification to users
    
    # =========================================================================
    # Per-User Risk Controls
    # =========================================================================
    
    async def check_user_daily_loss_limit(
        self,
        db: AsyncSession,
        user_id: int
    ) -> tuple[bool, Decimal]:
        """
        Check if user has exceeded daily loss limit.
        
        Returns:
            (exceeded, total_loss_today)
        """
        # Get today's trades
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = select(func.sum(Trade.realized_pnl_usd)).where(
            and_(
                Trade.user_id == user_id,
                Trade.exit_timestamp >= today_start,
                Trade.status == 'closed'
            )
        )
        
        result = await db.execute(query)
        total_pnl = result.scalar() or Decimal('0')
        
        # If profit, no issue
        if total_pnl >= 0:
            return False, total_pnl
        
        # Check loss limit
        total_loss = abs(total_pnl)
        
        # Get user's loss limit (would fetch from user settings)
        user_loss_limit = self.DEFAULT_DAILY_LOSS_LIMIT_USD
        
        exceeded = total_loss > user_loss_limit
        
        if exceeded:
            logger.warning(
                f"User {user_id} exceeded daily loss limit: "
                f"${total_loss} > ${user_loss_limit}"
            )
        
        return exceeded, total_loss
    
    async def apply_cooling_period(
        self,
        user_id: int,
        reason: str
    ):
        """
        Apply cooling period to user (pause copying for 24 hours).
        
        Args:
            user_id: User ID
            reason: Reason for cooling period
        """
        if not self.redis:
            await self.connect()
        
        cooling_key = f"user:{user_id}:cooling_period"
        
        await self.redis.setex(
            cooling_key,
            self.COOLING_PERIOD_HOURS * 3600,
            reason
        )
        
        logger.warning(
            f"Cooling period applied to user {user_id} for {self.COOLING_PERIOD_HOURS}h. "
            f"Reason: {reason}"
        )
        
        # TODO: Notify user
    
    # =========================================================================
    # Trader Watchdog
    # =========================================================================
    
    async def check_trader_suspicious_activity(
        self,
        db: AsyncSession,
        trader_address: str
    ) -> tuple[bool, List[str]]:
        """
        Monitor trader for suspicious activity.
        
        Returns:
            (is_suspicious, reasons)
        """
        reasons = []
        
        # Check 1: Sudden trade size spike
        recent_trades = await self._get_recent_trader_trades(db, trader_address, hours=24)
        older_trades = await self._get_recent_trader_trades(db, trader_address, hours=168, offset_hours=24)
        
        if recent_trades and older_trades:
            recent_avg_size = sum(t.entry_value_usd for t in recent_trades) / len(recent_trades)
            older_avg_size = sum(t.entry_value_usd for t in older_trades) / len(older_trades)
            
            if older_avg_size > 0 and recent_avg_size / older_avg_size > self.TRADE_SIZE_SPIKE_MULTIPLIER:
                reasons.append(
                    f"Trade size spike: {recent_avg_size / older_avg_size:.1f}x increase"
                )
        
        # Check 2: Large single-day loss
        today_pnl = await self._get_trader_daily_pnl(db, trader_address)
        if today_pnl < 0:
            # Get total portfolio value (would calculate properly)
            portfolio_value = Decimal('10000')  # Placeholder
            
            loss_percent = abs(today_pnl) / portfolio_value
            if loss_percent > self.SINGLE_DAY_LOSS_THRESHOLD:
                reasons.append(
                    f"Large single-day loss: {loss_percent * 100:.1f}%"
                )
        
        # Check 3: Abnormal trade frequency (would implement)
        
        is_suspicious = len(reasons) > 0
        
        if is_suspicious:
            logger.warning(
                f"Suspicious activity detected for trader {trader_address}: "
                f"{', '.join(reasons)}"
            )
        
        return is_suspicious, reasons
    
    async def pause_trader(
        self,
        trader_address: str,
        reason: str,
        paused_by: str = "system"
    ):
        """
        Pause all copying of a trader.
        
        Args:
            trader_address: Trader wallet address
            reason: Reason for pause
            paused_by: Who paused (user_id or 'system')
        """
        if not self.redis:
            await self.connect()
        
        pause_data = {
            "trader_address": trader_address,
            "reason": reason,
            "paused_at": datetime.utcnow().isoformat(),
            "paused_by": paused_by
        }
        
        await self.redis.hset(
            self.paused_traders_key,
            trader_address,
            str(pause_data)
        )
        
        logger.warning(
            f"Trader {trader_address} paused by {paused_by}. Reason: {reason}"
        )
        
        # TODO: Notify all users copying this trader
    
    async def is_trader_paused(self, trader_address: str) -> bool:
        """Check if trader is paused"""
        if not self.redis:
            await self.connect()
        
        return await self.redis.hexists(self.paused_traders_key, trader_address)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _get_recent_trader_trades(
        self,
        db: AsyncSession,
        trader_address: str,
        hours: int,
        offset_hours: int = 0
    ) -> List[Trade]:
        """Get recent trades for a trader"""
        end_time = datetime.utcnow() - timedelta(hours=offset_hours)
        start_time = end_time - timedelta(hours=hours)
        
        query = select(Trade).where(
            and_(
                Trade.trader_wallet_address == trader_address,
                Trade.entry_timestamp >= start_time,
                Trade.entry_timestamp < end_time
            )
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def _get_trader_daily_pnl(
        self,
        db: AsyncSession,
        trader_address: str
    ) -> Decimal:
        """Get trader's P&L for today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = select(func.sum(Trade.realized_pnl_usd)).where(
            and_(
                Trade.trader_wallet_address == trader_address,
                Trade.exit_timestamp >= today_start,
                Trade.status == 'closed'
            )
        )
        
        result = await db.execute(query)
        return result.scalar() or Decimal('0')


# Singleton instance
_risk_management_service: Optional[RiskManagementService] = None


def get_risk_management_service() -> RiskManagementService:
    """Get singleton instance"""
    global _risk_management_service
    if _risk_management_service is None:
        _risk_management_service = RiskManagementService()
    return _risk_management_service
