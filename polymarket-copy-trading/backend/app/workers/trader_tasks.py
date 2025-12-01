"""
Celery tasks for fetching and updating trader data from The Graph Protocol.

These tasks run periodically to keep our database synchronized with the latest
trader performance data from Polymarket. Tasks are designed for reliability
with proper error handling, retries, and monitoring.

Tasks:
- fetch_top_traders_task: Fetches top traders every 5 minutes
- update_trader_statistics_task: Updates detailed stats for specific traders
- calculate_leaderboard_task: Recalculates rankings every minute
- sync_trader_positions_task: Syncs position data for active traders
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from celery import Task
from celery.schedules import crontab
import redis
import json

from app.core.celery_app import celery_app
from app.db.session import async_session
from app.services.graph_client import graph_client
from app.services.trader_fetcher import TraderDataFetcher
from app.models.trader_v2 import TraderV2
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions for Async Task Execution
# ============================================================================

def run_async(coro):
    """
    Helper to run async coroutines in Celery tasks.
    
    Celery tasks are synchronous by default, so we need to run async code
    in an event loop.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


# ============================================================================
# Celery Tasks
# ============================================================================

@celery_app.task(
    name="fetch_top_traders_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60  # 1 minute
)
def fetch_top_traders_task(
    self: Task,
    limit: int = 100,
    timeframe_days: int = 7
) -> Dict[str, int]:
    """
    Scheduled task to fetch top traders from The Graph and update database.
    
    This is the main synchronization task that runs every 5 minutes to keep
    our trader data fresh. It fetches the top-performing traders and stores
    their stats in the database.
    
    Args:
        limit: Maximum number of traders to fetch (default: 100)
        timeframe_days: Activity window in days (default: 7)
        
    Returns:
        Summary dictionary with execution results
        
    Raises:
        Retry: On transient errors (network, timeout)
        
    Schedule:
        Every 5 minutes via Celery Beat
    """
    task_start = datetime.utcnow()
    logger.info(f"Starting fetch_top_traders_task: limit={limit}, timeframe={timeframe_days}d")
    
    async def _execute():
        async with async_session() as db:
            try:
                # Initialize fetcher
                fetcher = TraderDataFetcher(
                    db_session=db,
                    graph_client=graph_client,
                    batch_size=50
                )
                
                # Fetch and store traders
                result = await fetcher.fetch_and_store_top_traders(
                    limit=limit,
                    timeframe_days=timeframe_days
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Error in fetch_top_traders_task: {e}", exc_info=True)
                raise
    
    try:
        # Execute async task
        result = run_async(_execute())
        
        # Calculate execution time
        duration = (datetime.utcnow() - task_start).total_seconds()
        
        # Log results
        logger.info(
            f"fetch_top_traders_task completed in {duration:.2f}s: "
            f"fetched={result['traders_fetched']}, "
            f"new={result['new_traders']}, "
            f"updated={result['updated_traders']}, "
            f"errors={result['errors']}"
        )
        
        # Alert if execution took too long
        if duration > 30.0:
            logger.warning(f"Task took longer than 30s: {duration:.2f}s")
        
        # Store task result for monitoring
        _store_task_result(
            task_name="fetch_top_traders",
            status="success",
            duration=duration,
            details=result
        )
        
        return result
        
    except Exception as exc:
        # Log error
        logger.error(f"fetch_top_traders_task failed: {exc}", exc_info=True)
        
        # Store failure
        _store_task_result(
            task_name="fetch_top_traders",
            status="failed",
            duration=(datetime.utcnow() - task_start).total_seconds(),
            error=str(exc)
        )
        
        # Retry on transient errors
        if isinstance(exc, (ConnectionError, TimeoutError)):
            logger.info(f"Retrying task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=exc)
        
        # Don't retry on permanent errors
        raise


@celery_app.task(
    name="update_trader_statistics_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def update_trader_statistics_task(
    self: Task,
    wallet_addresses: List[str],
    days: int = 30
) -> Dict[str, int]:
    """
    Update detailed statistics for specific traders.
    
    This task is used to fetch and store time-series data (daily statistics)
    for traders that are being actively copied or monitored. It provides
    granular historical performance data.
    
    Args:
        wallet_addresses: List of Ethereum wallet addresses
        days: Number of days of history to fetch (default: 30)
        
    Returns:
        Summary with success/failure counts
        
    Schedule:
        On-demand or every 15 minutes for active traders
    """
    task_start = datetime.utcnow()
    logger.info(f"Starting update_trader_statistics_task for {len(wallet_addresses)} traders")
    
    async def _execute():
        async with async_session() as db:
            try:
                fetcher = TraderDataFetcher(
                    db_session=db,
                    graph_client=graph_client
                )
                
                summary = {"success": 0, "failed": 0, "errors": []}
                
                for wallet_address in wallet_addresses:
                    try:
                        success = await fetcher.fetch_trader_statistics(
                            wallet_address=wallet_address,
                            days=days
                        )
                        
                        if success:
                            summary["success"] += 1
                        else:
                            summary["failed"] += 1
                            
                    except Exception as e:
                        logger.error(f"Error updating stats for {wallet_address}: {e}")
                        summary["failed"] += 1
                        summary["errors"].append({
                            "wallet": wallet_address,
                            "error": str(e)
                        })
                
                return summary
                
            except Exception as e:
                logger.error(f"Error in update_trader_statistics_task: {e}", exc_info=True)
                raise
    
    try:
        result = run_async(_execute())
        
        duration = (datetime.utcnow() - task_start).total_seconds()
        logger.info(
            f"update_trader_statistics_task completed in {duration:.2f}s: "
            f"success={result['success']}, failed={result['failed']}"
        )
        
        _store_task_result(
            task_name="update_trader_statistics",
            status="success",
            duration=duration,
            details=result
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"update_trader_statistics_task failed: {exc}", exc_info=True)
        
        _store_task_result(
            task_name="update_trader_statistics",
            status="failed",
            duration=(datetime.utcnow() - task_start).total_seconds(),
            error=str(exc)
        )
        
        if isinstance(exc, (ConnectionError, TimeoutError)):
            raise self.retry(exc=exc)
        
        raise


@celery_app.task(name="calculate_leaderboard_task")
def calculate_leaderboard_task() -> Dict[str, int]:
    """
    Recalculate leaderboard rankings and cache results.
    
    This task runs frequently (every minute) to keep leaderboard data fresh.
    Results are cached in Redis for fast API responses.
    
    Calculates:
    - 7-day leaderboard
    - 30-day leaderboard (optional)
    - All-time leaderboard (optional)
    
    Returns:
        Summary with trader counts per leaderboard
        
    Schedule:
        Every 1 minute via Celery Beat
    """
    task_start = datetime.utcnow()
    logger.info("Starting calculate_leaderboard_task")
    
    async def _execute():
        async with async_session() as db:
            try:
                fetcher = TraderDataFetcher(
                    db_session=db,
                    graph_client=graph_client
                )
                
                # Calculate 7-day leaderboard
                leaderboard_7d = await fetcher.calculate_leaderboard_rankings()
                
                # Cache in Redis
                _cache_leaderboard("leaderboard:7d", leaderboard_7d, ttl=60)
                
                logger.info(f"Cached leaderboard with {len(leaderboard_7d)} traders")
                
                return {
                    "leaderboard_7d_count": len(leaderboard_7d)
                }
                
            except Exception as e:
                logger.error(f"Error in calculate_leaderboard_task: {e}", exc_info=True)
                raise
    
    try:
        result = run_async(_execute())
        
        duration = (datetime.utcnow() - task_start).total_seconds()
        logger.info(f"calculate_leaderboard_task completed in {duration:.2f}s")
        
        _store_task_result(
            task_name="calculate_leaderboard",
            status="success",
            duration=duration,
            details=result
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"calculate_leaderboard_task failed: {exc}", exc_info=True)
        
        _store_task_result(
            task_name="calculate_leaderboard",
            status="failed",
            duration=(datetime.utcnow() - task_start).total_seconds(),
            error=str(exc)
        )
        
        raise


@celery_app.task(name="sync_trader_positions_task", bind=True)
def sync_trader_positions_task(
    self: Task,
    wallet_addresses: Optional[List[str]] = None,
    limit: int = 50
) -> Dict[str, int]:
    """
    Sync market positions for traders.
    
    Fetches and stores detailed position data (open/closed positions) for
    specified traders or the top N traders.
    
    Args:
        wallet_addresses: Specific traders to sync (optional)
        limit: Number of top traders to sync if wallet_addresses not provided
        
    Returns:
        Summary with positions synced
        
    Schedule:
        Every 10 minutes for top traders
    """
    task_start = datetime.utcnow()
    logger.info(f"Starting sync_trader_positions_task")
    
    async def _execute():
        async with async_session() as db:
            try:
                fetcher = TraderDataFetcher(
                    db_session=db,
                    graph_client=graph_client
                )
                
                # Get traders to sync
                if not wallet_addresses:
                    # Get top traders from database
                    from sqlalchemy import select
                    stmt = select(TraderV2).order_by(
                        TraderV2.total_pnl.desc()
                    ).limit(limit)
                    result = await db.execute(stmt)
                    traders = result.scalars().all()
                    addresses = [t.wallet_address for t in traders]
                else:
                    addresses = wallet_addresses
                
                summary = {"traders": 0, "positions": 0, "errors": 0}
                
                for address in addresses:
                    try:
                        count = await fetcher.update_trader_markets(address)
                        summary["traders"] += 1
                        summary["positions"] += count
                    except Exception as e:
                        logger.error(f"Error syncing positions for {address}: {e}")
                        summary["errors"] += 1
                
                return summary
                
            except Exception as e:
                logger.error(f"Error in sync_trader_positions_task: {e}", exc_info=True)
                raise
    
    try:
        result = run_async(_execute())
        
        duration = (datetime.utcnow() - task_start).total_seconds()
        logger.info(
            f"sync_trader_positions_task completed in {duration:.2f}s: "
            f"traders={result['traders']}, positions={result['positions']}"
        )
        
        _store_task_result(
            task_name="sync_trader_positions",
            status="success",
            duration=duration,
            details=result
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"sync_trader_positions_task failed: {exc}", exc_info=True)
        
        _store_task_result(
            task_name="sync_trader_positions",
            status="failed",
            duration=(datetime.utcnow() - task_start).total_seconds(),
            error=str(exc)
        )
        
        if isinstance(exc, (ConnectionError, TimeoutError)):
            raise self.retry(exc=exc)
        
        raise


# ============================================================================
# Helper Functions
# ============================================================================

def _cache_leaderboard(key: str, data: List[Dict], ttl: int = 60):
    """
    Cache leaderboard data in Redis.
    
    Args:
        key: Redis cache key
        data: Leaderboard data to cache
        ttl: Time-to-live in seconds (default: 60)
    """
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        
        # Serialize to JSON
        serialized = json.dumps(data, default=str)
        
        # Store with TTL
        redis_client.setex(key, ttl, serialized)
        
        logger.debug(f"Cached {len(data)} records to {key} with {ttl}s TTL")
        
    except Exception as e:
        logger.error(f"Error caching leaderboard: {e}")


def _store_task_result(
    task_name: str,
    status: str,
    duration: float,
    details: Optional[Dict] = None,
    error: Optional[str] = None
):
    """
    Store task execution results for monitoring and audit.
    
    In a production system, this would store to a task_history table.
    For now, we just log it.
    
    Args:
        task_name: Name of the task
        status: "success" or "failed"
        duration: Execution time in seconds
        details: Additional details (optional)
        error: Error message if failed (optional)
    """
    result = {
        "task_name": task_name,
        "status": status,
        "duration": duration,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details,
        "error": error
    }
    
    # Log for now (in production, store to database)
    logger.info(f"Task result: {json.dumps(result)}")
    
    # TODO: Store in task_history table for dashboard analytics


def get_leaderboard_from_cache(key: str = "leaderboard:7d") -> Optional[List[Dict]]:
    """
    Retrieve cached leaderboard data from Redis.
    
    Args:
        key: Redis cache key (default: "leaderboard:7d")
        
    Returns:
        Leaderboard data or None if not cached
    """
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)
        
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving cached leaderboard: {e}")
        return None


# ============================================================================
# Manual Task Triggers
# ============================================================================

def trigger_full_sync():
    """
    Manually trigger a full synchronization of all trader data.
    
    This is useful for:
    - Initial data population
    - Recovery from outages
    - Manual refreshes
    
    Returns:
        Dictionary with queued task IDs
    """
    task_ids = {}
    
    # Fetch top traders
    task_ids['fetch_traders'] = fetch_top_traders_task.delay(limit=100, timeframe_days=7)
    
    # Calculate leaderboard
    task_ids['leaderboard'] = calculate_leaderboard_task.delay()
    
    # Sync positions for top 50
    task_ids['positions'] = sync_trader_positions_task.delay(limit=50)
    
    logger.info(f"Triggered full sync: {task_ids}")
    
    return task_ids


def trigger_trader_update(wallet_addresses: List[str]):
    """
    Manually trigger statistics update for specific traders.
    
    Args:
        wallet_addresses: List of wallet addresses to update
        
    Returns:
        Task ID
    """
    task_id = update_trader_statistics_task.delay(wallet_addresses=wallet_addresses, days=30)
    
    logger.info(f"Triggered trader update for {len(wallet_addresses)} addresses: {task_id}")
    
    return task_id
