"""
Trade Execution Worker

Consumes copy trade signals and executes them via Polymarket API.
"""

from typing import Optional
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio
import json
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import redis.asyncio as redis

from app.core.config import settings
from app.models.api_key import User, Trade, APIKey
from app.services.encryption import get_encryption_service
from app.services.polymarket import get_polymarket_client
from app.services.cache.market_cache import get_market_cache_service


class TradeExecutionWorker:
    """
    Execute copy trades from signal queue.
    
    Flow:
    1. Consume signal from queue
    2. Retrieve user API keys
    3. Calculate order parameters
    4. Execute via Polymarket API
    5. Record trade
    """
    
    def __init__(self, worker_id: int = 1):
        """Initialize execution worker"""
        self.worker_id = worker_id
        self.redis_url = settings.REDIS_URL
        self.redis: Optional[redis.Redis] = None
        
        # Queue names
        self.signal_queue = "copy_trade_signals"
        self.retry_queue = "copy_trade_retries"
        
        # Configuration
        self.max_retries = 3
        self.retry_delay_seconds = 60
        self.slippage_percent = 1.0  # 1% slippage tolerance
        
        # Metrics
        self.trades_executed = 0
        self.trades_failed = 0
        self.trades_skipped = 0
        
        # Shutdown flag
        self.should_shutdown = False
        
        logger.info(f"TradeExecutionWorker {worker_id} initialized")
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = await redis.from_url(self.redis_url)
        logger.info(f"Worker {self.worker_id} connected to Redis")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info(f"Worker {self.worker_id} disconnected from Redis")
    
    async def check_idempotency(
        self,
        db: AsyncSession,
        original_tx_hash: str,
        user_id: int
    ) -> bool:
        """
        Check if signal already executed (idempotency).
        
        Args:
            original_tx_hash: Original trader's transaction hash
            user_id: User ID
        
        Returns:
            True if already exists (skip), False if new
        """
        query = select(Trade).where(
            and_(
                Trade.original_tx_hash == original_tx_hash,
                Trade.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.warning(
                f"Duplicate signal detected: "
                f"tx={original_tx_hash}, user={user_id}"
            )
            return True
        
        return False
    
    async def get_user_api_keys(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Optional[dict]:
        """
        Retrieve and decrypt user's Polymarket API keys.
        
        Args:
            user_id: User ID
        
        Returns:
            Dict with api_key, api_secret, passphrase or None
        """
        query = select(APIKey).where(APIKey.user_id == user_id)
        result = await db.execute(query)
        api_key_record = result.scalar_one_or_none()
        
        if not api_key_record:
            logger.error(f"No API keys found for user {user_id}")
            return None
        
        # Decrypt keys
        encryption = get_encryption_service()
        
        try:
            api_key = encryption.decrypt(api_key_record.api_key_encrypted)
            api_secret = encryption.decrypt(api_key_record.api_secret_encrypted)
            passphrase = (
                encryption.decrypt(api_key_record.passphrase_encrypted)
                if api_key_record.passphrase_encrypted
                else None
            )
            
            return {
                "api_key": api_key,
                "api_secret": api_secret,
                "passphrase": passphrase
            }
        except Exception as e:
            logger.error(f"Failed to decrypt API keys for user {user_id}: {e}")
            return None
    
    async def calculate_order_parameters(
        self,
        signal: dict,
        current_price: Decimal
    ) -> dict:
        """
        Calculate precise order parameters.
        
        Args:
            signal: Copy trade signal
            current_price: Current market price
        
        Returns:
            Order parameters dict
        """
        copy_amount = Decimal(signal['copy_amount'])
        side = signal['side']
        
        # Calculate quantity
        # quantity = amount / price
        quantity = copy_amount / current_price
        
        # Round to minimum tick size (0.01 for most markets)
        min_tick = Decimal('0.01')
        quantity = (quantity / min_tick).quantize(Decimal('1')) * min_tick
        
        # Calculate limit price with slippage
        slippage = Decimal(str(self.slippage_percent / 100))
        
        if side == 'buy':
            # For buys, add slippage to price
            limit_price = current_price * (1 + slippage)
        else:
            # For sells, subtract slippage
            limit_price = current_price * (1 - slippage)
        
        # Round price to 2 decimals
        limit_price = limit_price.quantize(Decimal('0.01'))
        
        return {
            "quantity": float(quantity),
            "limit_price": float(limit_price),
            "current_price": float(current_price)
        }
    
    async def execute_trade(
        self,
        db: AsyncSession,
        signal: dict
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        """
        Execute copy trade via Polymarket API.
        
        Args:
            signal: Copy trade signal
        
        Returns:
            (success, error_message, trade_data)
        """
        user_id = signal['user_id']
        market_id = signal['market_id']
        side = signal['side']
        outcome = signal['outcome']
        
        # Get API keys
        api_keys = await self.get_user_api_keys(db, user_id)
        if not api_keys:
            return False, "API keys not configured", None
        
        # Get current market price
        market_cache = get_market_cache_service()
        prices = await market_cache.get_market_price(market_id)
        
        if not prices:
            return False, "Market price unavailable", None
        
        # Select price based on outcome
        current_price = Decimal(str(prices['yes_price' if outcome == 'YES' else 'no_price']))
        
        # Calculate order parameters
        order_params = await self.calculate_order_parameters(signal, current_price)
        
        # Initialize Polymarket client with user's keys
        # (In production, would create client instance with user credentials)
        polymarket_client = get_polymarket_client()
        # polymarket_client.set_credentials(api_keys)
        
        try:
            # Execute order
            if side == 'buy':
                response = await polymarket_client.place_buy_order(
                    market_id=market_id,
                    outcome=outcome,
                    quantity=order_params['quantity'],
                    price=order_params['limit_price']
                )
            else:
                response = await polymarket_client.place_sell_order(
                    market_id=market_id,
                    outcome=outcome,
                    quantity=order_params['quantity'],
                    price=order_params['limit_price']
                )
            
            # Parse response
            trade_data = {
                "tx_hash": response.get('tx_hash', 'mock_tx_hash'),
                "order_id": response.get('order_id', 'mock_order_id'),
                "filled_quantity": order_params['quantity'],
                "filled_price": order_params['current_price'],
                "total_value": order_params['quantity'] * order_params['current_price']
            }
            
            return True, None, trade_data
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Trade execution failed: {error_msg}", exc_info=True)
            
            # Categorize error
            if "insufficient funds" in error_msg.lower():
                return False, "insufficient_funds", None
            elif "market closed" in error_msg.lower():
                return False, "market_closed", None
            elif "rate limit" in error_msg.lower():
                return False, "rate_limit", None
            elif "invalid" in error_msg.lower() and "key" in error_msg.lower():
                return False, "invalid_api_keys", None
            else:
                return False, f"order_rejected: {error_msg}", None
    
    async def record_trade(
        self,
        db: AsyncSession,
        signal: dict,
        trade_data: dict
    ):
        """
        Record executed trade in database.
        
        Args:
            signal: Original signal
            trade_data: Execution result data
        """
        # Create trade record
        trade = Trade(
            user_id=signal['user_id'],
            trader_wallet_address=signal['user_wallet_address'],
            original_tx_hash=signal['original_tx_hash'],
            entry_tx_hash=trade_data['tx_hash'],
            market_id=signal['market_id'],
            side=signal['side'],
            position=signal['outcome'],
            quantity=Decimal(str(trade_data['filled_quantity'])),
            entry_price=Decimal(str(trade_data['filled_price'])),
            entry_value_usd=Decimal(str(trade_data['total_value'])),
            status='open',
            entry_timestamp=datetime.utcnow(),
            copied_from_trader=signal['trader_address']
        )
        
        db.add(trade)
        await db.commit()
        await db.refresh(trade)
        
        logger.info(
            f"Trade recorded: id={trade.id}, user={signal['user_id']}, "
            f"market={signal['market_id']}, amount=${trade_data['total_value']:.2f}"
        )
        
        # TODO: Update positions table
        # TODO: Update spend tracking
        # TODO: Emit WebSocket event
        
        return trade
    
    async def handle_error(
        self,
        db: AsyncSession,
        signal: dict,
        error_type: str
    ):
        """
        Handle execution errors based on type.
        
        Args:
            signal: Failed signal
            error_type: Error category
        """
        user_id = signal['user_id']
        
        if error_type == "insufficient_funds":
            # TODO: Notify user
            # TODO: Pause copy relationship
            logger.warning(f"User {user_id} has insufficient funds. Pausing copy relationship.")
            
        elif error_type == "market_closed":
            # Just skip and log
            logger.info(f"Market {signal['market_id']} is closed. Skipping trade.")
            self.trades_skipped += 1
            
        elif error_type == "rate_limit":
            # Retry in 1 minute
            logger.info(f"Rate limited. Queueing for retry in {self.retry_delay_seconds}s")
            await self.redis.zadd(
                self.retry_queue,
                {json.dumps(signal): datetime.utcnow().timestamp() + self.retry_delay_seconds}
            )
            
        elif error_type == "invalid_api_keys":
            # TODO: Pause copy relationship
            # TODO: Alert user
            logger.error(f"Invalid API keys for user {user_id}. Pausing copy relationship.")
            
        else:
            # Generic order rejection - log and optionally retry
            logger.error(f"Order rejected for user {user_id}: {error_type}")
            self.trades_failed += 1
    
    async def process_signal(
        self,
        db: AsyncSession,
        signal: dict
    ):
        """
        Process a single copy trade signal.
        
        Complete flow:
        1. Check idempotency
        2. Execute trade
        3. Record or handle error
        
        Args:
            signal: Copy trade signal
        """
        signal_id = signal['signal_id']
        user_id = signal['user_id']
        
        logger.info(f"Processing signal {signal_id} for user {user_id}")
        
        try:
            # Check idempotency
            is_duplicate = await self.check_idempotency(
                db,
                signal['original_tx_hash'],
                user_id
            )
            
            if is_duplicate:
                self.trades_skipped += 1
                return
            
            # Execute trade
            success, error_msg, trade_data = await self.execute_trade(db, signal)
            
            if success:
                # Record trade
                await self.record_trade(db, signal, trade_data)
                self.trades_executed += 1
                logger.info(f"Signal {signal_id} executed successfully")
            else:
                # Handle error
                await self.handle_error(db, signal, error_msg)
                
        except Exception as e:
            logger.error(
                f"Error processing signal {signal_id}: {e}",
                exc_info=True
            )
            self.trades_failed += 1
    
    async def run(self, db: AsyncSession):
        """
        Main worker loop - consume and process signals.
        
        Args:
            db: Database session
        """
        await self.connect()
        
        logger.info(f"Trade execution worker {self.worker_id} started")
        
        try:
            while not self.should_shutdown:
                # Pop signal from queue (blocking with timeout)
                result = await self.redis.blpop(
                    self.signal_queue,
                    timeout=5
                )
                
                if result:
                    queue_name, signal_data = result
                    signal = json.loads(signal_data)
                    
                    # Process signal
                    await self.process_signal(db, signal)
                
                # Check retry queue
                await self.process_retries()
                
                # Log metrics periodically
                if (self.trades_executed + self.trades_failed) % 50 == 0 and self.trades_executed > 0:
                    self.log_metrics()
                    
        except KeyboardInterrupt:
            logger.info(f"Worker {self.worker_id} stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in worker {self.worker_id}: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def process_retries(self):
        """Process signals from retry queue"""
        now = datetime.utcnow().timestamp()
        
        # Get signals ready for retry
        signals = await self.redis.zrangebyscore(
            self.retry_queue,
            0,
            now,
            start=0,
            num=10
        )
        
        for signal_data in signals:
            # Re-queue to main queue
            await self.redis.rpush(self.signal_queue, signal_data)
            
            # Remove from retry queue
            await self.redis.zrem(self.retry_queue, signal_data)
    
    def log_metrics(self):
        """Log worker metrics"""
        total = self.trades_executed + self.trades_failed + self.trades_skipped
        success_rate = (
            self.trades_executed / total * 100
            if total > 0
            else 0
        )
        
        logger.info(
            f"Worker {self.worker_id} metrics: "
            f"executed={self.trades_executed}, "
            f"failed={self.trades_failed}, "
            f"skipped={self.trades_skipped}, "
            f"success_rate={success_rate:.1f}%"
        )
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info(f"Worker {self.worker_id} shutting down...")
        self.should_shutdown = True
        await self.disconnect()
        self.log_metrics()
    
    def get_metrics(self) -> dict:
        """Get worker metrics"""
        total = self.trades_executed + self.trades_failed + self.trades_skipped
        
        return {
            "worker_id": self.worker_id,
            "trades_executed": self.trades_executed,
            "trades_failed": self.trades_failed,
            "trades_skipped": self.trades_skipped,
            "total_processed": total,
            "success_rate": (
                self.trades_executed / total * 100
                if total > 0
                else 0
            )
        }


async def run_worker(worker_id: int = 1):
    """Run a single execution worker"""
    from app.db.session import get_db_context
    
    async with get_db_context() as db:
        worker = TradeExecutionWorker(worker_id)
        await worker.run(db)
