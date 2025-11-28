"""
Execution Worker Tasks

Celery tasks for trade execution workers.
"""

from celery import shared_task
from loguru import logger


@shared_task(name="copy_trading.run_execution_worker")
def run_execution_worker_task(worker_id: int = 1):
    """
    Run trade execution worker (Celery task).
    
    Args:
        worker_id: Worker identifier
    """
    import asyncio
    from app.services.copy_trading.execution_worker import run_worker
    
    try:
        asyncio.run(run_worker(worker_id))
    except Exception as e:
        logger.error(f"Execution worker {worker_id} error: {e}", exc_info=True)
        raise


@shared_task(name="copy_trading.get_execution_metrics")
def get_execution_metrics():
    """Get execution worker metrics"""
    # In production, would aggregate metrics from all workers
    return {
        "message": "Metrics endpoint - implement with shared state (Redis)"
    }


@shared_task(name="copy_trading.health_check")
def health_check():
    """Worker health check"""
    from app.services.copy_trading.execution_worker import TradeExecutionWorker
    
    # Basic health check
    return {
        "status": "healthy",
        "service": "trade_execution_worker"
    }
