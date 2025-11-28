"""
Integration: Event Listener + Queue

Connects event listener to trade queue for complete pipeline.
"""

from loguru import logger

from app.services.blockchain.event_listener import (
    get_event_listener_service,
    ParsedTrade
)
from app.services.blockchain.trade_queue import get_trade_queue_service


async def setup_trade_pipeline():
    """
    Set up complete pipeline: blockchain events → queue → processing
    
    Example:
        ```python
        # In main.py or worker startup
        await setup_trade_pipeline()
        
        # Start listening
        listener = get_event_listener_service()
        await listener.start()
        ```
    """
    # Get services
    listener = get_event_listener_service()
    queue = get_trade_queue_service()
    
    # Connect queue
    await queue.connect()
    
    # Register callback to push trades to queue
    async def on_trade_detected(trade: ParsedTrade):
        """Callback when new trade is detected"""
        try:
            logger.info(
                f"New trade detected: {trade.trader_address[:10]}... "
                f"{trade.side} {trade.quantity} {trade.outcome} @ ${trade.price}"
            )
            
            # Determine priority based on trade value
            priority = 1 if trade.total_value > 1000 else 0
            
            # Push to queue
            success = await queue.push_trade(trade, priority=priority)
            
            if success:
                logger.info(f"Trade queued: {trade.tx_hash[:16]}...")
            else:
                logger.error(f"Failed to queue trade: {trade.tx_hash}")
                
        except Exception as e:
            logger.error(f"Error in trade callback: {e}")
    
    # Register callbacks
    listener.on_trade_detected(on_trade_detected)
    
    logger.info("Trade pipeline configured: Events → Queue → Processing")


async def get_pipeline_status():
    """
    Get status of entire pipeline.
    
    Returns:
        Dictionary with listener and queue status
    """
    listener = get_event_listener_service()
    queue = get_trade_queue_service()
    
    return {
        'listener': listener.get_status(),
        'queue': await queue.get_status()
    }
