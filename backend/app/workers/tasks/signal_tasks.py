"""
Signal Generation Worker

Celery task for running signal generation service.
"""

from celery import shared_task
from loguru import logger

from app.db.session import get_db_context
from app.services.copy_trading.signal_generation import get_signal_generation_service


@shared_task(name="copy_trading.process_trade_event")
def process_trade_event_task(trade_event: dict):
    """
    Process a single trade event (Celery task).
    
    Args:
        trade_event: Trade event from blockchain listener
    """
    import asyncio
    
    async def _process():
        async with get_db_context() as db:
            service = get_signal_generation_service()
            await service.process_trade_event(db, trade_event)
    
    try:
        asyncio.run(_process())
        logger.info(f"Processed trade event: {trade_event['tx_hash']}")
    except Exception as e:
        logger.error(f"Error processing trade event: {e}", exc_info=True)
        raise


@shared_task(name="copy_trading.run_signal_generation_service")
def run_signal_generation_service():
    """
    Run signal generation service continuously (scheduled task).
    
    This task runs in the background and processes trade events
    from the queue.
    """
    import asyncio
    
    async def _run():
        async with get_db_context() as db:
            service = get_signal_generation_service()
            await service.run(db)
    
    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error(f"Signal generation service error: {e}", exc_info=True)
        raise


@shared_task(name="copy_trading.get_signal_metrics")
def get_signal_metrics():
    """Get signal generation metrics"""
    service = get_signal_generation_service()
    metrics = service.get_metrics()
    
    logger.info(f"Signal generation metrics: {metrics}")
    return metrics
