"""
Trade Queue Service

Manages Redis queue for parsed trades with:
- Push trades to processing queue
- Dead letter queue for failed processing
- Retry mechanism with exponential backoff
- Queue monitoring
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings
from app.services.blockchain.event_listener import ParsedTrade


class TradeQueueService:
    """
    Manages Redis queue for trade processing.
    
    Queue Structure:
    - `trades:pending` - Main processing queue (list)
    - `trades:processing:{worker_id}` - Currently processing (hash)
    - `trades:failed` - Dead letter queue (list)
    - `trades:completed` - Successfully processed (sorted set by timestamp)
    
    Example:
        ```python
        queue = TradeQueueService()
        await queue.connect()
        
        # Push trade to queue
        await queue.push_trade(parsed_trade)
        
        # Consume trades
        async for trade in queue.consume_trades():
            # Process trade
            await process_trade(trade)
            await queue.mark_completed(trade.tx_hash)
        ```
    """
    
    # Queue names
    PENDING_QUEUE = "trades:pending"
    PROCESSING_PREFIX = "trades:processing"
    FAILED_QUEUE = "trades:failed"
    COMPLETED_SET = "trades:completed"
    RETRY_QUEUE = "trades:retry"
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 5  # seconds
    PROCESSING_TIMEOUT = 300  # 5 minutes
    
    def __init__(self):
        """Initialize queue service"""
        self.redis_client: Optional[redis.Redis] = None
        self.worker_id: str = f"worker_{id(self)}"
        
        # Statistics
        self.total_pushed: int = 0
        self.total_consumed: int = 0
        self.total_completed: int = 0
        self.total_failed: int = 0
        
        logger.info(f"TradeQueueService initialized (worker: {self.worker_id})")
    
    async def connect(self):
        """Connect to Redis"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis for trade queue")
    
    async def push_trade(
        self,
        trade: ParsedTrade,
        priority: int = 0
    ) -> bool:
        """
        Push trade to processing queue.
        
        Args:
            trade: Parsed trade to queue
            priority: Priority (higher = more important, 0 = normal)
            
        Returns:
            True if successfully queued
        """
        try:
            await self.connect()
            
            # Serialize trade
            trade_data = {
                **trade.to_dict(),
                'queued_at': datetime.utcnow().isoformat(),
                'retry_count': 0,
                'priority': priority
            }
            
            trade_json = json.dumps(trade_data)
            
            # Push to queue (LPUSH = add to left, RPOP = consume from right = FIFO)
            if priority > 0:
                # High priority: add to left (will be consumed first)
                await self.redis_client.lpush(self.PENDING_QUEUE, trade_json)
            else:
                # Normal priority: add to right
                await self.redis_client.rpush(self.PENDING_QUEUE, trade_json)
            
            self.total_pushed += 1
            
            logger.debug(
                f"Queued trade: {trade.tx_hash[:16]}... "
                f"(priority: {priority}, queue size: {await self.get_queue_size()})"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue trade: {e}")
            return False
    
    async def consume_trades(
        self,
        batch_size: int = 10,
        timeout: int = 5
    ):
        """
        Consume trades from queue (async generator).
        
        Args:
            batch_size: Max trades to fetch at once
            timeout: Timeout for blocking pop (seconds)
            
        Yields:
            ParsedTrade objects
        """
        await self.connect()
        
        while True:
            try:
                # Pop from queue (BRPOP = blocking right pop)
                result = await self.redis_client.brpop(
                    self.PENDING_QUEUE,
                    timeout=timeout
                )
                
                if not result:
                    # Timeout, no trades available
                    await asyncio.sleep(1)
                    continue
                
                queue_name, trade_json = result
                
                # Parse trade
                trade_data = json.loads(trade_json)
                trade = self._deserialize_trade(trade_data)
                
                # Mark as processing
                await self._mark_processing(trade)
                
                self.total_consumed += 1
                
                yield trade
                
            except asyncio.CancelledError:
                logger.info("Trade consumer cancelled")
                break
            except Exception as e:
                logger.error(f"Error consuming trade: {e}")
                await asyncio.sleep(5)
    
    async def mark_completed(
        self,
        tx_hash: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Mark trade as successfully processed.
        
        Args:
            tx_hash: Transaction hash
            metadata: Optional completion metadata
        """
        try:
            await self.connect()
            
            # Remove from processing
            processing_key = f"{self.PROCESSING_PREFIX}:{self.worker_id}"
            await self.redis_client.hdel(processing_key, tx_hash)
            
            # Add to completed set (with timestamp as score)
            timestamp = datetime.utcnow().timestamp()
            await self.redis_client.zadd(
                self.COMPLETED_SET,
                {tx_hash: timestamp}
            )
            
            # Store metadata if provided
            if metadata:
                await self.redis_client.hset(
                    f"trades:metadata:{tx_hash}",
                    mapping=metadata
                )
                # Expire after 7 days
                await self.redis_client.expire(
                    f"trades:metadata:{tx_hash}",
                    7 * 24 * 60 * 60
                )
            
            self.total_completed += 1
            
            logger.debug(f"Marked trade as completed: {tx_hash[:16]}...")
            
        except Exception as e:
            logger.error(f"Failed to mark trade as completed: {e}")
    
    async def mark_failed(
        self,
        trade: ParsedTrade,
        error: str,
        retry: bool = True
    ):
        """
        Mark trade as failed.
        
        Args:
            trade: Failed trade
            error: Error message
            retry: Whether to retry or move to DLQ
        """
        try:
            await self.connect()
            
            # Remove from processing
            processing_key = f"{self.PROCESSING_PREFIX}:{self.worker_id}"
            await self.redis_client.hdel(processing_key, trade.tx_hash)
            
            # Get current retry count
            trade_data = trade.to_dict()
            retry_count = trade_data.get('retry_count', 0)
            
            if retry and retry_count < self.MAX_RETRIES:
                # Retry with exponential backoff
                retry_count += 1
                trade_data['retry_count'] = retry_count
                trade_data['last_error'] = error
                trade_data['retry_at'] = (
                    datetime.utcnow() + 
                    timedelta(seconds=self.RETRY_DELAY_BASE ** retry_count)
                ).isoformat()
                
                # Add to retry queue
                await self.redis_client.lpush(
                    self.RETRY_QUEUE,
                    json.dumps(trade_data)
                )
                
                logger.warning(
                    f"Trade failed, scheduling retry {retry_count}/{self.MAX_RETRIES}: "
                    f"{trade.tx_hash[:16]}... - {error}"
                )
            else:
                # Move to dead letter queue
                trade_data['retry_count'] = retry_count
                trade_data['final_error'] = error
                trade_data['failed_at'] = datetime.utcnow().isoformat()
                
                await self.redis_client.lpush(
                    self.FAILED_QUEUE,
                    json.dumps(trade_data)
                )
                
                self.total_failed += 1
                
                logger.error(
                    f"Trade permanently failed after {retry_count} retries: "
                    f"{trade.tx_hash[:16]}... - {error}"
                )
                
        except Exception as e:
            logger.error(f"Failed to mark trade as failed: {e}")
    
    async def _mark_processing(self, trade: ParsedTrade):
        """Mark trade as currently processing"""
        processing_key = f"{self.PROCESSING_PREFIX}:{self.worker_id}"
        
        processing_data = {
            'started_at': datetime.utcnow().isoformat(),
            'worker_id': self.worker_id,
            'tx_hash': trade.tx_hash
        }
        
        await self.redis_client.hset(
            processing_key,
            trade.tx_hash,
            json.dumps(processing_data)
        )
        
        # Set expiration in case worker crashes
        await self.redis_client.expire(processing_key, self.PROCESSING_TIMEOUT)
    
    def _deserialize_trade(self, data: Dict[str, Any]) -> ParsedTrade:
        """Deserialize trade from dict"""
        # Convert string decimals back to Decimal
        data['quantity'] = Decimal(str(data['quantity']))
        data['price'] = Decimal(str(data['price']))
        data['total_value'] = Decimal(str(data['total_value']))
        data['fees'] = Decimal(str(data['fees']))
        
        # Remove queue-specific fields
        data.pop('queued_at', None)
        data.pop('retry_count', None)
        data.pop('priority', None)
        data.pop('retry_at', None)
        data.pop('last_error', None)
        
        return ParsedTrade(**data)
    
    async def get_queue_size(self) -> int:
        """Get number of trades in pending queue"""
        await self.connect()
        return await self.redis_client.llen(self.PENDING_QUEUE)
    
    async def get_failed_count(self) -> int:
        """Get number of trades in failed queue"""
        await self.connect()
        return await self.redis_client.llen(self.FAILED_QUEUE)
    
    async def get_completed_count(self) -> int:
        """Get number of completed trades"""
        await self.connect()
        return await self.redis_client.zcard(self.COMPLETED_SET)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get queue status"""
        await self.connect()
        
        return {
            'pending_count': await self.get_queue_size(),
            'failed_count': await self.get_failed_count(),
            'completed_count': await self.get_completed_count(),
            'total_pushed': self.total_pushed,
            'total_consumed': self.total_consumed,
            'total_completed': self.total_completed,
            'total_failed': self.total_failed,
            'worker_id': self.worker_id
        }
    
    async def retry_failed_trades(self, limit: int = 100) -> int:
        """
        Retry failed trades from DLQ.
        
        Args:
            limit: Max trades to retry
            
        Returns:
            Number of trades requeued
        """
        await self.connect()
        
        requeued = 0
        
        for _ in range(limit):
            # Pop from failed queue
            result = await self.redis_client.rpop(self.FAILED_QUEUE)
            
            if not result:
                break
            
            # Re-add to pending queue
            await self.redis_client.lpush(self.PENDING_QUEUE, result)
            requeued += 1
        
        logger.info(f"Requeued {requeued} failed trades")
        return requeued
    
    async def clear_old_completed(self, days: int = 7):
        """
        Clear completed trades older than specified days.
        
        Args:
            days: Age threshold in days
        """
        await self.connect()
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_timestamp = cutoff.timestamp()
        
        # Remove from sorted set
        removed = await self.redis_client.zremrangebyscore(
            self.COMPLETED_SET,
            0,
            cutoff_timestamp
        )
        
        logger.info(f"Cleared {removed} completed trades older than {days} days")
        return removed
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Trade queue connection closed")


# Singleton instance
_trade_queue_service: Optional[TradeQueueService] = None


def get_trade_queue_service() -> TradeQueueService:
    """Get singleton instance of TradeQueueService"""
    global _trade_queue_service
    if _trade_queue_service is None:
        _trade_queue_service = TradeQueueService()
    return _trade_queue_service
