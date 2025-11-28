"""
Reconciliation Tasks

Celery tasks for trade reconciliation.
"""

from celery import shared_task
from loguru import logger


@shared_task(name="reconciliation.run_reconciliation_cycle")
def run_reconciliation_cycle_task():
    """
    Run trade reconciliation cycle (scheduled every 5 minutes).
    """
    import asyncio
    from app.db.session import get_db_context
    from app.services.reconciliation.trade_reconciliation import get_reconciliation_service
    
    async def _run():
        async with get_db_context() as db:
            service = get_reconciliation_service()
            results = await service.run_reconciliation_cycle(db)
            return len(results)
    
    try:
        num_processed = asyncio.run(_run())
        logger.info(f"Reconciliation cycle processed {num_processed} trades")
        return {"processed": num_processed}
    except Exception as e:
        logger.error(f"Reconciliation cycle error: {e}", exc_info=True)
        raise


@shared_task(name="reconciliation.generate_daily_report")
def generate_daily_report_task():
    """
    Generate daily reconciliation report (scheduled daily at midnight).
    """
    import asyncio
    from app.db.session import get_db_context
    from app.services.reconciliation.trade_reconciliation import get_reconciliation_service
    
    async def _run():
        async with get_db_context() as db:
            service = get_reconciliation_service()
            report = await service.generate_daily_report(db)
            return report
    
    try:
        report = asyncio.run(_run())
        logger.info(f"Daily reconciliation report generated: {report}")
        
        # TODO: Send report via email
        
        return report
    except Exception as e:
        logger.error(f"Daily report generation error: {e}", exc_info=True)
        raise
