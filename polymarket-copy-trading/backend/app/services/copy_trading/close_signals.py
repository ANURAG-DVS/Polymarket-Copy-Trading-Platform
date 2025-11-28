"""
Position Close Signal Generation

Detects when a copied trader closes a position and generates close signals.
"""

from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import json

from app.models.api_key import Trade
from app.services.copy_trading.signal_generation import CopyTradeSignal


@dataclass
class CloseSignal:
    """Position close signal"""
    # User info
    user_id: int
    user_wallet_address: str
    
    # Original position
    original_trade_id: int
    trader_address: str
    original_close_tx_hash: str
    
    # Position details
    market_id: str
    outcome: str  # YES/NO
    
    # Close parameters
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal  # User's quantity to close
    close_percentage: Decimal  # 0-100 (100 = full close)
    
    # Metadata
    timestamp: datetime
    signal_id: str
    
    def to_dict(self) -> dict:
        """Convert to dict for queue"""
        return {
            "user_id": self.user_id,
            "user_wallet_address": self.user_wallet_address,
            "original_trade_id": self.original_trade_id,
            "trader_address": self.trader_address,
            "original_close_tx_hash": self.original_close_tx_hash,
            "market_id": self.market_id,
            "outcome": self.outcome,
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price),
            "quantity": str(self.quantity),
            "close_percentage": str(self.close_percentage),
            "timestamp": self.timestamp.isoformat(),
            "signal_id": self.signal_id
        }


class CloseSignalService:
    """
    Generate position close signals.
    
    Flow:
    1. Detect trader sell transaction
    2. Find matching open positions for copying users
    3. Calculate exit parameters
    4. Generate close signals
    """
    
    def __init__(self):
        """Initialize service"""
        logger.info("CloseSignalService initialized")
    
    async def get_matching_positions(
        self,
        db: AsyncSession,
        trader_address: str,
        market_id: str,
        outcome: str
    ) -> List[Trade]:
        """
        Find all open positions that match the trader's close.
        
        Query: SELECT * FROM trades 
               WHERE copied_from_trader = ? 
               AND market_id = ? 
               AND position = ?
               AND status = 'open'
        
        Args:
            trader_address: Trader wallet address
            market_id: Market ID
            outcome: YES/NO
        
        Returns:
            List of matching open trades
        """
        query = select(Trade).where(
            and_(
                Trade.copied_from_trader == trader_address,
                Trade.market_id == market_id,
                Trade.position == outcome,
                Trade.status == 'open'
            )
        )
        
        result = await db.execute(query)
        positions = result.scalars().all()
        
        logger.info(
            f"Found {len(positions)} open positions matching trader close: "
            f"trader={trader_address}, market={market_id}, outcome={outcome}"
        )
        
        return positions
    
    async def calculate_close_quantity(
        self,
        position: Trade,
        trader_close_quantity: Decimal,
        trader_original_quantity: Decimal
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate quantity to close for user's position.
        
        Handles partial closes:
        - If trader closes 100% → close 100% of user position
        - If trader closes 50% → close 50% of user position
        
        Args:
            position: User's open position
            trader_close_quantity: Quantity trader is closing
            trader_original_quantity: Trader's original position size
        
        Returns:
            (close_quantity, close_percentage)
        """
        # Calculate close percentage
        close_percentage = (trader_close_quantity / trader_original_quantity) * 100
        
        # Calculate user's close quantity
        user_position_quantity = position.quantity
        close_quantity = user_position_quantity * (close_percentage / 100)
        
        logger.info(
            f"Calculated close: position_id={position.id}, "
            f"close_pct={close_percentage}%, "
            f"close_qty={close_quantity}"
        )
        
        return close_quantity, Decimal(str(close_percentage))
    
    async def calculate_realized_pnl(
        self,
        entry_price: Decimal,
        exit_price: Decimal,
        quantity: Decimal,
        side: str
    ) -> Decimal:
        """
        Calculate realized P&L.
        
        Formula: (exit_price - entry_price) × quantity
        
        For sells (short positions), reverse the calculation.
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            quantity: Quantity
            side: 'buy' or 'sell'
        
        Returns:
            Realized P&L in USD
        """
        if side == 'buy':
            # Long position: profit when exit > entry
            pnl = (exit_price - entry_price) * quantity
        else:
            # Short position: profit when entry > exit
            pnl = (entry_price - exit_price) * quantity
        
        # TODO: Subtract fees
        # pnl -= trading_fees
        
        return pnl
    
    async def generate_close_signal(
        self,
        db: AsyncSession,
        position: Trade,
        exit_price: Decimal,
        close_quantity: Decimal,
        close_percentage: Decimal,
        original_close_tx_hash: str
    ) -> CloseSignal:
        """
        Generate a close signal for a position.
        
        Args:
            position: Open position to close
            exit_price: Exit price
            close_quantity: Quantity to close
            close_percentage: Percentage of position to close
            original_close_tx_hash: Trader's close transaction hash
        
        Returns:
            CloseSignal object
        """
        import uuid
        
        signal = CloseSignal(
            user_id=position.user_id,
            user_wallet_address=position.trader_wallet_address,
            original_trade_id=position.id,
            trader_address=position.copied_from_trader,
            original_close_tx_hash=original_close_tx_hash,
            market_id=position.market_id,
            outcome=position.position,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=close_quantity,
            close_percentage=close_percentage,
            timestamp=datetime.utcnow(),
            signal_id=str(uuid.uuid4())
        )
        
        return signal
    
    async def process_trader_close(
        self,
        db: AsyncSession,
        close_event: dict
    ) -> List[CloseSignal]:
        """
        Process a trader's position close event.
        
        Flow:
        1. Find matching open positions
        2. Calculate close quantities
        3. Generate close signals
        4. Handle edge cases
        
        Args:
            close_event: Trader's close event from blockchain
        
        Returns:
            List of generated close signals
        """
        trader_address = close_event['trader_address']
        market_id = close_event['market_id']
        outcome = close_event['outcome']
        exit_price = Decimal(str(close_event['price']))
        trader_close_quantity = Decimal(str(close_event['quantity']))
        tx_hash = close_event['tx_hash']
        
        logger.info(
            f"Processing trader close: trader={trader_address}, "
            f"market={market_id}, qty={trader_close_quantity}"
        )
        
        # Find matching positions
        positions = await self.get_matching_positions(
            db,
            trader_address,
            market_id,
            outcome
        )
        
        if not positions:
            logger.info("No matching positions found")
            return []
        
        # Generate close signals
        signals = []
        
        # Get trader's original position size (would query from database)
        # For now, assume full close
        trader_original_quantity = trader_close_quantity
        
        for position in positions:
            try:
                # Check if user manually closed
                if position.status != 'open':
                    logger.info(
                        f"Position {position.id} already closed manually. Skipping."
                    )
                    continue
                
                # Calculate close quantity
                close_quantity, close_percentage = await self.calculate_close_quantity(
                    position,
                    trader_close_quantity,
                    trader_original_quantity
                )
                
                # Generate signal
                signal = await self.generate_close_signal(
                    db,
                    position,
                    exit_price,
                    close_quantity,
                    close_percentage,
                    tx_hash
                )
                
                signals.append(signal)
                
                logger.info(
                    f"Generated close signal: signal_id={signal.signal_id}, "
                    f"user={signal.user_id}, qty={close_quantity}"
                )
                
            except Exception as e:
                logger.error(
                    f"Error generating close signal for position {position.id}: {e}",
                    exc_info=True
                )
        
        return signals
    
    async def publish_close_signals(
        self,
        redis,
        signals: List[CloseSignal]
    ):
        """
        Publish close signals to execution queue.
        
        Args:
            redis: Redis connection
            signals: List of close signals
        """
        queue_name = "position_close_signals"
        
        for signal in signals:
            await redis.rpush(
                queue_name,
                json.dumps(signal.to_dict())
            )
            
            logger.info(
                f"Published close signal {signal.signal_id} to queue"
            )


async def execute_close_signal(
    db: AsyncSession,
    close_signal: dict
):
    """
    Execute a position close signal.
    
    This integrates with the execution worker.
    
    Args:
        close_signal: Close signal from queue
    """
    from app.services.copy_trading.execution_worker import TradeExecutionWorker
    
    # Convert close signal to sell trade signal
    sell_signal = {
        "user_id": close_signal['user_id'],
        "user_wallet_address": close_signal['user_wallet_address'],
        "trader_address": close_signal['trader_address'],
        "original_tx_hash": close_signal['original_close_tx_hash'],
        "market_id": close_signal['market_id'],
        "side": "sell",
        "outcome": close_signal['outcome'],
        "original_amount": str(
            Decimal(close_signal['quantity']) * Decimal(close_signal['exit_price'])
        ),
        "copy_amount": str(
            Decimal(close_signal['quantity']) * Decimal(close_signal['exit_price'])
        ),
        "proportionality": "1.0",  # Already calculated
        "max_price": close_signal['exit_price'],
        "priority": "high",
        "timestamp": close_signal['timestamp'],
        "signal_id": close_signal['signal_id']
    }
    
    # Execute via worker
    worker = TradeExecutionWorker()
    await worker.connect()
    
    try:
        # Execute sell order
        success, error_msg, trade_data = await worker.execute_trade(db, sell_signal)
        
        if success:
            # Update original trade record
            await update_trade_on_close(
                db,
                close_signal['original_trade_id'],
                Decimal(close_signal['exit_price']),
                Decimal(close_signal['quantity']),
                trade_data['tx_hash']
            )
            
            logger.info(
                f"Position closed successfully: trade_id={close_signal['original_trade_id']}"
            )
        else:
            logger.error(
                f"Failed to close position {close_signal['original_trade_id']}: {error_msg}"
            )
            
    finally:
        await worker.disconnect()


async def update_trade_on_close(
    db: AsyncSession,
    trade_id: int,
    exit_price: Decimal,
    close_quantity: Decimal,
    exit_tx_hash: str
):
    """
    Update trade record when position is closed.
    
    Args:
        trade_id: Trade ID
        exit_price: Exit price
        close_quantity: Quantity closed
        exit_tx_hash: Exit transaction hash
    """
    # Get trade
    query = select(Trade).where(Trade.id == trade_id)
    result = await db.execute(query)
    trade = result.scalar_one()
    
    # Calculate P&L
    service = CloseSignalService()
    realized_pnl = await service.calculate_realized_pnl(
        trade.entry_price,
        exit_price,
        close_quantity,
        trade.side
    )
    
    realized_pnl_percent = (realized_pnl / trade.entry_value_usd) * 100
    
    # Check if full close or partial
    close_percentage = (close_quantity / trade.quantity) * 100
    
    if close_percentage >= 99:  # Full close (with rounding tolerance)
        # Update trade to closed
        trade.exit_price = exit_price
        trade.exit_value_usd = exit_price * close_quantity
        trade.exit_tx_hash = exit_tx_hash
        trade.exit_timestamp = datetime.utcnow()
        trade.realized_pnl_usd = realized_pnl
        trade.realized_pnl_percent = realized_pnl_percent
        trade.status = 'closed'
    else:
        # Partial close - reduce quantity
        # TODO: Create separate trade record for closed portion
        logger.info(
            f"Partial close ({close_percentage}%) for trade {trade_id}. "
            "Full implementation needed for position splitting."
        )
    
    await db.commit()
    
    logger.info(
        f"Trade {trade_id} updated: "
        f"exit_price={exit_price}, "
        f"realized_pnl=${realized_pnl:.2f}, "
        f"status={trade.status}"
    )
    
    # TODO: Send notification with P&L result
    # TODO: Update user's total P&L in analytics


# Singleton instance
_close_signal_service: Optional[CloseSignalService] = None


def get_close_signal_service() -> CloseSignalService:
    """Get singleton instance"""
    global _close_signal_service
    if _close_signal_service is None:
        _close_signal_service = CloseSignalService()
    return _close_signal_service
