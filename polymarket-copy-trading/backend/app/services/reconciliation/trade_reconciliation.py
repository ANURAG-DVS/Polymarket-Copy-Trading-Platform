"""
Trade Reconciliation Service

Reconciles executed trades with on-chain outcomes and API confirmations.
"""

from typing import Optional, List, Dict
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from web3 import Web3

from app.models.api_key import Trade
from app.services.polymarket import get_polymarket_client
from app.core.config import settings


@dataclass
class ReconciliationResult:
    """Reconciliation result for a trade"""
    trade_id: int
    previous_status: str
    new_status: str
    discrepancy_detected: bool
    discrepancy_details: Optional[str]
    action_taken: str  # updated, retried, alerted, none


class TradeReconciliationService:
    """
    Reconcile trades with Polymarket API and blockchain.
    
    Features:
    - Periodic status checks
    - Discrepancy detection
    - Automatic retries
    - User notifications
    """
    
    # Configuration
    RECONCILIATION_INTERVAL_MINUTES = 5
    PENDING_TIMEOUT_MINUTES = 5
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAYS = [60, 300, 900]  # 1 min, 5 min, 15 min
    PRICE_DISCREPANCY_THRESHOLD = Decimal('0.10')  # 10%
    
    def __init__(self):
        """Initialize reconciliation service"""
        self.reconciled_count = 0
        self.failed_count = 0
        self.discrepancy_count = 0
        
        logger.info("TradeReconciliationService initialized")
    
    async def get_pending_trades(
        self,
        db: AsyncSession
    ) -> List[Trade]:
        """
        Query trades with pending or submitted status.
        
        Returns:
            List of trades to reconcile
        """
        query = select(Trade).where(
            Trade.status.in_(['pending', 'submitted'])
        ).order_by(Trade.entry_timestamp)
        
        result = await db.execute(query)
        trades = result.scalars().all()
        
        logger.info(f"Found {len(trades)} trades to reconcile")
        
        return trades
    
    async def check_polymarket_order_status(
        self,
        order_id: str,
        user_api_keys: dict
    ) -> Dict:
        """
        Check order status via Polymarket API.
        
        Args:
            order_id: Order ID
            user_api_keys: User's API credentials
        
        Returns:
            Order status dict
        """
        polymarket_client = get_polymarket_client()
        # polymarket_client.set_credentials(user_api_keys)
        
        try:
            order_status = await polymarket_client.get_order_status(order_id)
            
            return {
                "status": order_status.get('status', 'unknown'),  # filled, rejected, pending
                "filled_quantity": Decimal(str(order_status.get('filled_quantity', 0))),
                "average_price": Decimal(str(order_status.get('average_price', 0))),
                "last_updated": datetime.fromisoformat(order_status.get('updated_at', datetime.utcnow().isoformat()))
            }
        except Exception as e:
            logger.error(f"Failed to check order status for {order_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_blockchain_confirmation(
        self,
        tx_hash: str
    ) -> Optional[Dict]:
        """
        Check transaction confirmation on blockchain.
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            Confirmation details or None
        """
        try:
            w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
            
            # Get transaction receipt
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            
            if receipt:
                return {
                    "confirmed": True,
                    "block_number": receipt['blockNumber'],
                    "confirmations": w3.eth.block_number - receipt['blockNumber'],
                    "status": "success" if receipt['status'] == 1 else "failed"
                }
            else:
                return {"confirmed": False}
                
        except Exception as e:
            logger.error(f"Failed to check blockchain for {tx_hash}: {e}")
            return None
    
    async def detect_price_discrepancy(
        self,
        trade: Trade,
        actual_price: Decimal
    ) -> tuple[bool, Optional[str]]:
        """
        Detect if actual price differs significantly from expected.
        
        Args:
            trade: Trade record
            actual_price: Actual execution price
        
        Returns:
            (has_discrepancy, details)
        """
        expected_price = trade.entry_price
        
        if actual_price == 0:
            return False, None
        
        # Calculate price difference percentage
        price_diff = abs(actual_price - expected_price) / expected_price
        
        if price_diff > self.PRICE_DISCREPANCY_THRESHOLD:
            details = (
                f"Price discrepancy: expected={expected_price}, "
                f"actual={actual_price}, "
                f"difference={price_diff * 100:.2f}%"
            )
            logger.warning(f"Trade {trade.id}: {details}")
            return True, details
        
        return False, None
    
    async def update_trade_status(
        self,
        db: AsyncSession,
        trade: Trade,
        new_status: str,
        actual_price: Optional[Decimal] = None,
        confirmation_block: Optional[int] = None
    ):
        """
        Update trade status and related fields.
        
        Args:
            trade: Trade to update
            new_status: New status
            actual_price: Actual execution price
            confirmation_block: Blockchain confirmation block
        """
        trade.status = new_status
        
        if actual_price:
            trade.entry_price = actual_price
            trade.entry_value_usd = actual_price * trade.quantity
        
        if confirmation_block:
            trade.confirmation_block_number = confirmation_block
        
        if new_status == 'confirmed':
            trade.confirmed_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(
            f"Trade {trade.id} updated: status={new_status}, "
            f"price={actual_price}, block={confirmation_block}"
        )
    
    async def schedule_retry(
        self,
        db: AsyncSession,
        trade: Trade
    ):
        """
        Schedule trade for retry with exponential backoff.
        
        Args:
            trade: Trade to retry
        """
        # Increment retry count
        retry_count = trade.retry_count if hasattr(trade, 'retry_count') else 0
        retry_count += 1
        
        if retry_count > self.MAX_RETRY_ATTEMPTS:
            # Max retries exceeded
            trade.status = 'permanently_failed'
            trade.retry_count = retry_count
            await db.commit()
            
            logger.error(
                f"Trade {trade.id} permanently failed after {retry_count} attempts"
            )
            
            # TODO: Notify user
            return
        
        # Calculate retry delay
        delay_seconds = self.RETRY_DELAYS[retry_count - 1] if retry_count <= len(self.RETRY_DELAYS) else 900
        retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        trade.status = 'retry_scheduled'
        trade.retry_count = retry_count
        trade.retry_at = retry_at
        await db.commit()
        
        logger.info(
            f"Trade {trade.id} scheduled for retry {retry_count}/{self.MAX_RETRY_ATTEMPTS} "
            f"at {retry_at} (in {delay_seconds}s)"
        )
        
        # TODO: Add to retry queue
    
    async def reconcile_trade(
        self,
        db: AsyncSession,
        trade: Trade,
        user_api_keys: Optional[dict] = None
    ) -> ReconciliationResult:
        """
        Reconcile a single trade.
        
        Flow:
        1. Check Polymarket API status
        2. Check blockchain confirmation
        3. Update trade status
        4. Detect discrepancies
        5. Take action (update, retry, alert)
        
        Args:
            trade: Trade to reconcile
            user_api_keys: User's API keys (optional)
        
        Returns:
            ReconciliationResult
        """
        previous_status = trade.status
        action_taken = "none"
        discrepancy_detected = False
        discrepancy_details = None
        
        # Check API status
        if trade.order_id and user_api_keys:
            api_status = await self.check_polymarket_order_status(
                trade.order_id,
                user_api_keys
            )
            
            if api_status['status'] == 'filled':
                # Order filled
                actual_price = api_status['average_price']
                
                # Check for price discrepancy
                has_discrepancy, details = await self.detect_price_discrepancy(
                    trade,
                    actual_price
                )
                
                if has_discrepancy:
                    discrepancy_detected = True
                    discrepancy_details = details
                    self.discrepancy_count += 1
                
                # Update to confirmed
                await self.update_trade_status(
                    db,
                    trade,
                    'confirmed',
                    actual_price=actual_price
                )
                
                action_taken = "updated_to_confirmed"
                self.reconciled_count += 1
                
            elif api_status['status'] == 'rejected':
                # Order rejected
                await self.update_trade_status(db, trade, 'failed')
                
                # TODO: Refund spend limit
                
                action_taken = "updated_to_failed"
                self.failed_count += 1
                
            elif api_status['status'] == 'pending':
                # Still pending - check timeout
                pending_duration = datetime.utcnow() - trade.entry_timestamp
                
                if pending_duration > timedelta(minutes=self.PENDING_TIMEOUT_MINUTES):
                    # Timeout - schedule retry
                    await self.schedule_retry(db, trade)
                    action_taken = "scheduled_retry"
                else:
                    action_taken = "still_pending"
        
        # Check blockchain confirmation
        if trade.entry_tx_hash:
            blockchain_status = await self.check_blockchain_confirmation(
                trade.entry_tx_hash
            )
            
            if blockchain_status and blockchain_status['confirmed']:
                if blockchain_status['status'] == 'success':
                    # Transaction successful
                    await self.update_trade_status(
                        db,
                        trade,
                        trade.status,  # Keep current status
                        confirmation_block=blockchain_status['block_number']
                    )
                    
                    if action_taken == "none":
                        action_taken = "blockchain_confirmed"
                else:
                    # Transaction failed on-chain
                    await self.update_trade_status(db, trade, 'failed')
                    action_taken = "blockchain_failed"
                    self.failed_count += 1
        
        return ReconciliationResult(
            trade_id=trade.id,
            previous_status=previous_status,
            new_status=trade.status,
            discrepancy_detected=discrepancy_detected,
            discrepancy_details=discrepancy_details,
            action_taken=action_taken
        )
    
    async def run_reconciliation_cycle(
        self,
        db: AsyncSession
    ) -> List[ReconciliationResult]:
        """
        Run a complete reconciliation cycle.
        
        Args:
            db: Database session
        
        Returns:
            List of reconciliation results
        """
        logger.info("Starting reconciliation cycle...")
        
        # Reset counters
        self.reconciled_count = 0
        self.failed_count = 0
        self.discrepancy_count = 0
        
        # Get pending trades
        pending_trades = await self.get_pending_trades(db)
        
        results = []
        
        for trade in pending_trades:
            try:
                # Get user API keys (would fetch from database)
                user_api_keys = None  # Placeholder
                
                # Reconcile trade
                result = await self.reconcile_trade(db, trade, user_api_keys)
                results.append(result)
                
            except Exception as e:
                logger.error(
                    f"Error reconciling trade {trade.id}: {e}",
                    exc_info=True
                )
        
        # Log summary
        logger.info(
            f"Reconciliation cycle complete: "
            f"processed={len(pending_trades)}, "
            f"reconciled={self.reconciled_count}, "
            f"failed={self.failed_count}, "
            f"discrepancies={self.discrepancy_count}"
        )
        
        return results
    
    async def generate_daily_report(
        self,
        db: AsyncSession
    ) -> Dict:
        """
        Generate daily reconciliation report.
        
        Returns:
            Report dict with metrics
        """
        # Calculate date range
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        
        # Query reconciled trades from today
        query = select(Trade).where(
            and_(
                Trade.confirmed_at >= start_of_day,
                Trade.status == 'confirmed'
            )
        )
        
        result = await db.execute(query)
        confirmed_trades = result.scalars().all()
        
        # Calculate metrics
        total_trades = len(confirmed_trades)
        
        if total_trades > 0:
            # Average confirmation time
            confirmation_times = [
                (trade.confirmed_at - trade.entry_timestamp).total_seconds()
                for trade in confirmed_trades
                if trade.confirmed_at
            ]
            avg_confirmation_time = sum(confirmation_times) / len(confirmation_times)
            
            # Success rate (would need total attempts)
            success_rate = 100.0  # Placeholder
        else:
            avg_confirmation_time = 0
            success_rate = 0
        
        report = {
            "date": today.isoformat(),
            "total_confirmed": total_trades,
            "avg_confirmation_time_seconds": avg_confirmation_time,
            "success_rate_percent": success_rate,
            "discrepancies_detected": self.discrepancy_count,
            "failed_trades": self.failed_count
        }
        
        logger.info(f"Daily reconciliation report: {report}")
        
        return report


# Singleton instance
_reconciliation_service: Optional[TradeReconciliationService] = None


def get_reconciliation_service() -> TradeReconciliationService:
    """Get singleton instance"""
    global _reconciliation_service
    if _reconciliation_service is None:
        _reconciliation_service = TradeReconciliationService()
    return _reconciliation_service
