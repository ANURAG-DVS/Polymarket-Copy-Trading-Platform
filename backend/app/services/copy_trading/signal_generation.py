"""
Copy Trade Signal Generation Service

Detects trader actions and generates validated copy trade signals.
"""

from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis
import json

from app.core.config import settings
from app.models.api_key import User
from app.services.subscription import get_subscription_service, SubscriptionTier


@dataclass
class CopyTradeSignal:
    """Copy trade signal for execution"""
    # User info
    user_id: int
    user_wallet_address: str
    
    # Original trade
    trader_address: str
    original_tx_hash: str
    
    # Trade details
    market_id: str
    side: str  # buy/sell
    outcome: str  # YES/NO
    
    # Amounts
    original_amount: Decimal
    copy_amount: Decimal
    proportionality: Decimal
    
    # Execution params
    max_price: Optional[Decimal]
    priority: str  # high/medium/low
    
    # Metadata
    timestamp: datetime
    signal_id: str
    
    def to_dict(self) -> dict:
        """Convert to dict for queue"""
        return {
            "user_id": self.user_id,
            "user_wallet_address": self.user_wallet_address,
            "trader_address": self.trader_address,
            "original_tx_hash": self.original_tx_hash,
            "market_id": self.market_id,
            "side": self.side,
            "outcome": self.outcome,
            "original_amount": str(self.original_amount),
            "copy_amount": str(self.copy_amount),
            "proportionality": str(self.proportionality),
            "max_price": str(self.max_price) if self.max_price else None,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "signal_id": self.signal_id
        }


class SignalGenerationService:
    """
    Generate copy trade signals from trader activities.
    
    Flow:
    1. Subscribe to trade event queue
    2. Check if trader is being copied
    3. Calculate copy amounts
    4. Validate signals
    5. Publish to execution queue
    """
    
    def __init__(self):
        """Initialize signal generation service"""
        self.redis_url = settings.REDIS_URL
        self.redis: Optional[redis.Redis] = None
        
        # Queue names
        self.trade_event_queue = "trade_events"
        self.signal_queue = "copy_trade_signals"
        
        # Metrics
        self.signals_generated = 0
        self.signals_validated = 0
        self.signals_rejected = 0
        
        logger.info("SignalGenerationService initialized")
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = await redis.from_url(self.redis_url)
        logger.info("Connected to Redis for signal generation")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")
    
    async def get_active_copy_relationships(
        self,
        db: AsyncSession,
        trader_address: str
    ) -> List[dict]:
        """
        Get all active copy relationships for a trader.
        
        Query: SELECT user_id, proportionality, max_investment 
               FROM copy_relationships 
               WHERE trader_address = ? AND status = 'active'
        
        Returns:
            List of copy relationship configs
        """
        # In production, query copy_relationships table
        # For now, return empty list (placeholder)
        
        # query = select(CopyRelationship).where(
        #     and_(
        #         CopyRelationship.trader_address == trader_address,
        #         CopyRelationship.status == 'active',
        #         CopyRelationship.is_active == True,
        #         CopyRelationship.paused == False
        #     )
        # )
        # result = await db.execute(query)
        # relationships = result.scalars().all()
        
        # return [
        #     {
        #         "user_id": rel.user_id,
        #         "user_wallet_address": rel.user.wallet_address,
        #         "proportionality": rel.copy_percentage / 100,
        #         "max_investment": rel.max_investment_usd
        #     }
        #     for rel in relationships
        # ]
        
        return []
    
    async def calculate_copy_amount(
        self,
        original_amount: Decimal,
        proportionality: Decimal,
        max_investment: Optional[Decimal]
    ) -> Decimal:
        """
        Calculate copy trade amount.
        
        Formula: copy_amount = original_amount * proportionality
        
        Args:
            original_amount: Original trade size in USD
            proportionality: Copy percentage (0.0 - 1.0)
            max_investment: Maximum investment per trade (optional)
        
        Returns:
            Copy trade amount
        """
        copy_amount = original_amount * proportionality
        
        # Apply max investment limit
        if max_investment and copy_amount > max_investment:
            copy_amount = max_investment
            logger.info(
                f"Copy amount capped at max investment: "
                f"calculated={original_amount * proportionality}, max={max_investment}"
            )
        
        return copy_amount
    
    async def validate_signal(
        self,
        db: AsyncSession,
        signal: CopyTradeSignal
    ) -> tuple[bool, Optional[str]]:
        """
        Validate copy trade signal.
        
        Checks:
        1. User subscription limits
        2. User has sufficient funds/spend limit
        3. Market is still open
        
        Returns:
            (is_valid, rejection_reason)
        """
        subscription_service = get_subscription_service()
        
        # Get user
        query = select(User).where(User.id == signal.user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        # Check subscription tier
        tier = SubscriptionTier(
            user.subscription_tier 
            if hasattr(user, 'subscription_tier') 
            else 'free'
        )
        
        # Get user's monthly volume (would query from database)
        current_monthly_volume = Decimal('0')
        
        # Check volume limit
        allowed, message = subscription_service.check_volume_limit(
            tier,
            current_monthly_volume,
            signal.copy_amount
        )
        
        if not allowed:
            return False, f"Volume limit exceeded: {message}"
        
        # Check market is still open (would query market data)
        # market = await market_cache.get_market(signal.market_id)
        # if not market or not market.is_active:
        #     return False, "Market is closed or expired"
        
        # Check user has sufficient balance (would query Polymarket API)
        # user_balance = await get_user_balance(signal.user_wallet_address)
        # if user_balance < signal.copy_amount:
        #     return False, f"Insufficient balance: {user_balance} < {signal.copy_amount}"
        
        return True, None
    
    async def generate_signal(
        self,
        db: AsyncSession,
        trade_event: dict,
        relationship: dict
    ) -> CopyTradeSignal:
        """
        Generate copy trade signal from trade event and relationship.
        
        Args:
            trade_event: Original trade event from blockchain
            relationship: Copy relationship configuration
        
        Returns:
            CopyTradeSignal object
        """
        # Calculate copy amount
        original_amount = Decimal(trade_event['amount_usd'])
        proportionality = Decimal(str(relationship['proportionality']))
        max_investment = (
            Decimal(str(relationship['max_investment'])) 
            if relationship.get('max_investment') 
            else None
        )
        
        copy_amount = await self.calculate_copy_amount(
            original_amount,
            proportionality,
            max_investment
        )
        
        # Generate signal ID
        import uuid
        signal_id = str(uuid.uuid4())
        
        # Create signal
        signal = CopyTradeSignal(
            user_id=relationship['user_id'],
            user_wallet_address=relationship['user_wallet_address'],
            trader_address=trade_event['trader_address'],
            original_tx_hash=trade_event['tx_hash'],
            market_id=trade_event['market_id'],
            side=trade_event['side'],
            outcome=trade_event['outcome'],
            original_amount=original_amount,
            copy_amount=copy_amount,
            proportionality=proportionality,
            max_price=Decimal(str(trade_event['price'])) if 'price' in trade_event else None,
            priority="high",  # Time-sensitive
            timestamp=datetime.utcnow(),
            signal_id=signal_id
        )
        
        self.signals_generated += 1
        
        return signal
    
    async def publish_signal(self, signal: CopyTradeSignal):
        """
        Publish signal to execution queue.
        
        Args:
            signal: Validated copy trade signal
        """
        if not self.redis:
            raise RuntimeError("Redis not connected")
        
        # Publish to signal queue
        await self.redis.rpush(
            self.signal_queue,
            json.dumps(signal.to_dict())
        )
        
        logger.info(
            f"Published signal {signal.signal_id} to execution queue: "
            f"user={signal.user_id}, amount=${signal.copy_amount}"
        )
        
        # Track in database (would insert into trade_queue table)
        # await db.execute(
        #     insert(TradeQueue).values(
        #         signal_id=signal.signal_id,
        #         user_id=signal.user_id,
        #         status='queued',
        #         created_at=datetime.utcnow()
        #     )
        # )
    
    async def process_trade_event(
        self,
        db: AsyncSession,
        trade_event: dict
    ):
        """
        Process a single trade event.
        
        Flow:
        1. Get active copy relationships
        2. Generate signals for each
        3. Validate signals
        4. Publish valid signals
        
        Args:
            trade_event: Trade event from blockchain listener
        """
        trader_address = trade_event['trader_address']
        
        logger.info(
            f"Processing trade event: trader={trader_address}, "
            f"tx={trade_event['tx_hash']}"
        )
        
        # Get copy relationships
        relationships = await self.get_active_copy_relationships(
            db,
            trader_address
        )
        
        if not relationships:
            logger.debug(f"No active copy relationships for {trader_address}")
            return
        
        logger.info(
            f"Found {len(relationships)} copy relationships for {trader_address}"
        )
        
        # Generate and validate signals
        for relationship in relationships:
            try:
                # Generate signal
                signal = await self.generate_signal(
                    db,
                    trade_event,
                    relationship
                )
                
                # Validate signal
                is_valid, rejection_reason = await self.validate_signal(
                    db,
                    signal
                )
                
                if is_valid:
                    # Publish to execution queue
                    await self.publish_signal(signal)
                    self.signals_validated += 1
                else:
                    # Log rejection
                    logger.warning(
                        f"Signal rejected for user {signal.user_id}: "
                        f"{rejection_reason}"
                    )
                    self.signals_rejected += 1
                    
                    # TODO: Notify user about skipped signal
                    
            except Exception as e:
                logger.error(
                    f"Error processing signal for user {relationship['user_id']}: {e}",
                    exc_info=True
                )
                self.signals_rejected += 1
    
    async def run(self, db: AsyncSession):
        """
        Main event loop - subscribe to trade events and process.
        
        Args:
            db: Database session
        """
        await self.connect()
        
        logger.info("Signal generation service started. Listening for trade events...")
        
        try:
            while True:
                # Pop trade event from queue (blocking with timeout)
                result = await self.redis.blpop(
                    self.trade_event_queue,
                    timeout=5
                )
                
                if result:
                    queue_name, event_data = result
                    trade_event = json.loads(event_data)
                    
                    # Process event
                    await self.process_trade_event(db, trade_event)
                
                # Log metrics periodically
                if self.signals_generated % 100 == 0 and self.signals_generated > 0:
                    logger.info(
                        f"Signal generation metrics: "
                        f"generated={self.signals_generated}, "
                        f"validated={self.signals_validated}, "
                        f"rejected={self.signals_rejected}"
                    )
                    
        except KeyboardInterrupt:
            logger.info("Signal generation service stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in signal generation service: {e}", exc_info=True)
        finally:
            await self.disconnect()
    
    def get_metrics(self) -> dict:
        """Get service metrics"""
        return {
            "signals_generated": self.signals_generated,
            "signals_validated": self.signals_validated,
            "signals_rejected": self.signals_rejected,
            "rejection_rate": (
                self.signals_rejected / self.signals_generated * 100
                if self.signals_generated > 0
                else 0
            )
        }


# Singleton instance
_signal_service: Optional[SignalGenerationService] = None


def get_signal_generation_service() -> SignalGenerationService:
    """Get singleton instance"""
    global _signal_service
    if _signal_service is None:
        _signal_service = SignalGenerationService()
    return _signal_service
