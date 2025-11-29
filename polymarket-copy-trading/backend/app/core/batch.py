import asyncio
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.models.trade import Trade
from app.core.metrics import Metrics
import logging

logger = logging.getLogger(__name__)

class BatchTradeExecutor:
    """Batch trade execution for improved performance"""
    
    def __init__(self, batch_size: int = 50, flush_interval: float = 1.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.pending_trades: List[Dict] = []
        self._lock = asyncio.Lock()
        self._flush_task = None
    
    async def start(self):
        """Start the batch executor"""
        if not self._flush_task:
            self._flush_task = asyncio.create_task(self._periodic_flush())
    
    async def stop(self):
        """Stop the batch executor and flush remaining trades"""
        if self._flush_task:
            self._flush_task.cancel()
            await self.flush()
    
    async def add_trade(self, trade_data: Dict):
        """Add trade to batch"""
        async with self._lock:
            self.pending_trades.append(trade_data)
            
            if len(self.pending_trades) >= self.batch_size:
                await self._flush()
    
    async def flush(self):
        """Flush all pending trades"""
        async with self._lock:
            await self._flush()
    
    async def _flush(self):
        """Internal flush method (must be called with lock held)"""
        if not self.pending_trades:
            return
        
        trades_to_process = self.pending_trades.copy()
        self.pending_trades.clear()
        
        try:
            # Process trades in parallel
            tasks = [self._execute_trade(trade) for trade in trades_to_process]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            error_count = len(results) - success_count
            
            Metrics.increment('trade.batch.executed', value=success_count)
            if error_count > 0:
                Metrics.increment('trade.batch.errors', value=error_count)
            
            logger.info(f"Batch executed: {success_count} success, {error_count} errors")
        
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            Metrics.increment('trade.batch.critical_error')
    
    async def _execute_trade(self, trade_data: Dict):
        """Execute a single trade"""
        # Implement actual trade execution logic
        # This is a placeholder
        await asyncio.sleep(0.01)  # Simulate API call
        return trade_data
    
    async def _periodic_flush(self):
        """Periodically flush pending trades"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic flush error: {e}")

class BulkDatabaseUpdater:
    """Bulk database updates for better performance"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def update_trades_batch(self, trade_updates: List[Dict]):
        """Update multiple trades in a single query"""
        if not trade_updates:
            return
        
        try:
            # Build bulk update statement
            stmt = update(Trade)
            
            # Execute bulk update
            for trade_update in trade_updates:
                await self.db.execute(
                    stmt.where(Trade.id == trade_update['id']).values(
                        status=trade_update.get('status'),
                        current_price=trade_update.get('current_price'),
                        unrealized_pnl=trade_update.get('unrealized_pnl'),
                        updated_at=trade_update.get('updated_at')
                    )
                )
            
            await self.db.commit()
            
            Metrics.increment('database.bulk_update', value=len(trade_updates))
            logger.info(f"Bulk updated {len(trade_updates)} trades")
        
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Bulk update failed: {e}")
            raise

# Global batch executor instance
batch_executor = BatchTradeExecutor(batch_size=100, flush_interval=0.5)
