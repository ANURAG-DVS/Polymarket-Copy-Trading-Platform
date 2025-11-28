"""
Spend Limit Enforcer Service

Tracks and enforces spending limits for Polymarket API keys:
- Daily/weekly spend limits
- Per-trade limits
- Automatic reset of limit windows
- Real-time spend tracking
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_service import get_audit_service, AuditAction
from loguru import logger


class SpendLimitExceededError(Exception):
    """Raised when a trade would exceed spend limits"""
    pass


class SpendLimitEnforcerService:
    """
    Enforces spending limits on Polymarket API keys.
    
    Features:
    - Pre-trade spend checks
    - Post-trade spend updates
    - Automatic daily/weekly limit resets
    - Multiple limit types (daily, per-trade, total exposure)
    """
    
    def __init__(self):
        self.audit_service = get_audit_service()
        logger.info("SpendLimitEnforcerService initialized")
    
    async def check_spend_limit(
        self,
        db: AsyncSession,
        user_id: int,
        key_id: int,
        trade_amount_usd: Decimal
    ) -> None:
        """
        Check if a trade would exceed spending limits.
        
        Validates against:
        1. API key daily spend limit
        2. User's max trade size
        3. User's max total exposure (open positions)
        
        Args:
            db: Database session
            user_id: User's unique ID
            key_id: API key ID
            trade_amount_usd: Proposed trade amount in USD
            
        Raises:
            SpendLimitExceededError: If any limit would be exceeded
        """
        from app.models.api_key import APIKey
        from app.models.user import User
        from app.models.trade import Trade
        
        # Fetch API key
        result = await db.execute(
            select(APIKey).where(
                and_(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ValueError(f"API key {key_id} not found")
        
        # Check if daily limit needs reset
        await self._reset_daily_limit_if_needed(db, api_key)
        
        # 1. Check API key daily spend limit
        remaining_daily = Decimal(str(api_key.daily_spend_limit_usd)) - Decimal(str(api_key.daily_spent_usd))
        if trade_amount_usd > remaining_daily:
            raise SpendLimitExceededError(
                f"Trade amount ${trade_amount_usd} exceeds remaining daily limit "
                f"${remaining_daily} (limit: ${api_key.daily_spend_limit_usd})"
            )
        
        # Fetch user limits
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # 2. Check user's max trade size
        if trade_amount_usd > Decimal(str(user.max_trade_size_usd)):
            raise SpendLimitExceededError(
                f"Trade amount ${trade_amount_usd} exceeds max trade size "
                f"${user.max_trade_size_usd} (tier: {user.subscription_tier})"
            )
        
        # 3. Check total exposure (sum of open positions)
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.copying_user_id == user_id,
                    Trade.status == 'open'
                )
            )
        )
        open_trades = result.scalars().all()
        
        total_exposure = sum(
            Decimal(str(trade.entry_value_usd)) for trade in open_trades
        )
        
        new_exposure = total_exposure + trade_amount_usd
        max_exposure = Decimal(str(user.max_total_exposure_usd))
        
        if new_exposure > max_exposure:
            raise SpendLimitExceededError(
                f"Trade would bring total exposure to ${new_exposure}, "
                f"exceeding limit ${max_exposure} (current: ${total_exposure})"
            )
        
        logger.debug(
            f"Spend check passed for user {user_id}: "
            f"trade=${trade_amount_usd}, daily_remaining=${remaining_daily}, "
            f"exposure=${total_exposure}/${max_exposure}"
        )
    
    async def update_spend_tracking(
        self,
        db: AsyncSession,
        user_id: int,
        key_id: int,
        trade_amount_usd: Decimal,
        trade_id: Optional[int] = None
    ) -> None:
        """
        Update spend tracking after trade execution.
        
        Args:
            db: Database session
            user_id: User's unique ID
            key_id: API key ID
            trade_amount_usd: Executed trade amount in USD
            trade_id: Optional trade ID for audit trail
        """
        from app.models.api_key import APIKey
        
        # Fetch API key
        result = await db.execute(
            select(APIKey).where(
                and_(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ValueError(f"API key {key_id} not found")
        
        # Update spending
        api_key.daily_spent_usd = Decimal(str(api_key.daily_spent_usd)) + trade_amount_usd
        api_key.total_volume_usd = Decimal(str(api_key.total_volume_usd)) + trade_amount_usd
        api_key.total_trades_executed += 1
        api_key.last_used_at = datetime.utcnow()
        
        await db.flush()
        
        # Audit log
        await self.audit_service.log(
            db=db,
            user_id=user_id,
            action=AuditAction.SPEND_UPDATED,
            resource_type='api_key',
            resource_id=str(key_id),
            details={
                'amount_usd': float(trade_amount_usd),
                'daily_spent_usd': float(api_key.daily_spent_usd),
                'trade_id': trade_id
            }
        )
        
        logger.info(
            f"Updated spend tracking for user {user_id}: "
            f"added ${trade_amount_usd}, daily_spent=${api_key.daily_spent_usd}"
        )
    
    async def _reset_daily_limit_if_needed(
        self,
        db: AsyncSession,
        api_key
    ) -> None:
        """
        Reset daily spend limit if 24 hours have passed.
        
        Args:
            db: Database session
            api_key: APIKey model instance
        """
        now = datetime.utcnow()
        time_since_reset = now - api_key.last_reset_at
        
        if time_since_reset >= timedelta(hours=24):
            api_key.daily_spent_usd = Decimal('0')
            api_key.last_reset_at = now
            await db.flush()
            
            logger.info(f"Reset daily spend limit for API key {api_key.id}")
    
    async def get_spend_limits_status(
        self,
        db: AsyncSession,
        user_id: int,
        key_id: Optional[int] = None
    ) -> dict:
        """
        Get current spend limits and usage for a user.
        
        Args:
            db: Database session
            user_id: User's unique ID
            key_id: Optional specific key ID (defaults to primary)
            
        Returns:
            Dictionary with limits and current usage
        """
        from app.models.api_key import APIKey
        from app.models.user import User
        from app.models.trade import Trade
        
        # Fetch API key
        query = select(APIKey).where(
            and_(APIKey.user_id == user_id, APIKey.status == 'active')
        )
        if key_id:
            query = query.where(APIKey.id == key_id)
        else:
            query = query.order_by(APIKey.is_primary.desc())
        
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return {'error': 'No active API key found'}
        
        # Fetch user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        # Calculate current exposure
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.copying_user_id == user_id,
                    Trade.status == 'open'
                )
            )
        )
        open_trades = result.scalars().all()
        current_exposure = sum(
            Decimal(str(trade.entry_value_usd)) for trade in open_trades
        )
        
        return {
            'api_key_id': api_key.id,
            'daily_limit_usd': float(api_key.daily_spend_limit_usd),
            'daily_spent_usd': float(api_key.daily_spent_usd),
            'daily_remaining_usd': float(
                Decimal(str(api_key.daily_spend_limit_usd)) - 
                Decimal(str(api_key.daily_spent_usd))
            ),
            'last_reset_at': api_key.last_reset_at.isoformat(),
            'max_trade_size_usd': float(user.max_trade_size_usd),
            'max_total_exposure_usd': float(user.max_total_exposure_usd),
            'current_exposure_usd': float(current_exposure),
            'exposure_remaining_usd': float(
                Decimal(str(user.max_total_exposure_usd)) - current_exposure
            ),
            'subscription_tier': user.subscription_tier,
            'total_trades_executed': api_key.total_trades_executed,
            'total_volume_usd': float(api_key.total_volume_usd)
        }


# Singleton instance
_spend_limit_service: Optional[SpendLimitEnforcerService] = None


def get_spend_limit_service() -> SpendLimitEnforcerService:
    """Get singleton instance of SpendLimitEnforcerService"""
    global _spend_limit_service
    if _spend_limit_service is None:
        _spend_limit_service = SpendLimitEnforcerService()
    return _spend_limit_service
