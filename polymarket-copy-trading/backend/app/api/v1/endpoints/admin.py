"""
Admin API endpoints for manual task triggering and system management.

These endpoints allow administrators to manually trigger background tasks,
view system status, and perform administrative operations.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.workers.trader_tasks import (
    fetch_top_traders_task,
    update_trader_statistics_task,
    calculate_leaderboard_task,
    sync_trader_positions_task,
    trigger_full_sync,
    trigger_trader_update
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TriggerTraderFetchRequest(BaseModel):
    """Request model for triggering trader fetch."""
    limit: int = 100
    timeframe_days: int = 7


class TriggerStatsUpdateRequest(BaseModel):
    """Request model for updating trader statistics."""
    wallet_addresses: List[str]
    days: int = 30


class TaskResponse(BaseModel):
    """Response model for queued tasks."""
    message: str
    task_id: Optional[str] = None
    task_ids: Optional[Dict[str, str]] = None


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.post("/trigger-trader-fetch", response_model=TaskResponse)
async def trigger_trader_fetch_manual(
    request: TriggerTraderFetchRequest = TriggerTraderFetchRequest()
):
    """
    Manually trigger trader data fetch task.
    
    This endpoint queues a Celery task to fetch top traders from The Graph Protocol
    and update the database immediately, without waiting for the scheduled run.
    
    **Admin only**: This endpoint should be protected in production
    
    Args:
        request: Configuration for the fetch task
        
    Returns:
        Task ID for tracking
        
    Example:
        POST /admin/trigger-trader-fetch
        {
            "limit": 100,
            "timeframe_days": 7
        }
    """
    try:
        # Queue the task
        task = fetch_top_traders_task.delay(
            limit=request.limit,
            timeframe_days=request.timeframe_days
        )
        
        return TaskResponse(
            message="Trader fetch task queued successfully",
            task_id=str(task.id)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.post("/trigger-stats-update", response_model=TaskResponse)
async def trigger_stats_update_manual(request: TriggerStatsUpdateRequest):
    """
    Manually trigger statistics update for specific traders.
    
    Use this to fetch detailed daily statistics for traders you're actively monitoring.
    
    Args:
        request: List of wallet addresses and days of history
        
    Returns:
        Task ID for tracking
        
    Example:
        POST /admin/trigger-stats-update
        {
            "wallet_addresses": ["0x123...", "0xabc..."],
            "days": 30
        }
    """
    try:
        task = update_trader_statistics_task.delay(
            wallet_addresses=request.wallet_addresses,
            days=request.days
        )
        
        return TaskResponse(
            message=f"Statistics update queued for {len(request.wallet_addresses)} traders",
            task_id=str(task.id)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.post("/trigger-leaderboard-calc", response_model=TaskResponse)
async def trigger_leaderboard_calculation():
    """
    Manually trigger leaderboard re-calculation.
    
    Forces an immediate recalculation of leaderboard rankings and caches the results.
    Useful after bulk data updates or for testing.
    
    Returns:
        Task ID for tracking
        
    Example:
        POST /admin/trigger-leaderboard-calc
    """
    try:
        task = calculate_leaderboard_task.delay()
        
        return TaskResponse(
            message="Leaderboard calculation task queued",
            task_id=str(task.id)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.post("/trigger-positions-sync", response_model=TaskResponse)
async def trigger_positions_sync(
    wallet_addresses: Optional[List[str]] = None,
    limit: int = 50
):
    """
    Manually trigger trader positions synchronization.
    
    Fetches and stores market position data for specified traders or top N traders.
    
    Args:
        wallet_addresses: Specific traders to sync (optional)
        limit: Number of top traders to sync if addresses not provided
        
    Returns:
        Task ID for tracking
        
    Example:
        POST /admin/trigger-positions-sync?limit=50
    """
    try:
        task = sync_trader_positions_task.delay(
            wallet_addresses=wallet_addresses,
            limit=limit
        )
        
        return TaskResponse(
            message="Positions sync task queued",
            task_id=str(task.id)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.post("/trigger-full-sync", response_model=TaskResponse)
async def trigger_full_sync_manual():
    """
    Trigger a complete synchronization of all trader data.
    
    This queues multiple tasks:
    - Fetch top traders
    - Calculate leaderboard
    - Sync positions for top 50 traders
    
    **Use with caution**: This can be resource-intensive
    
    Returns:
        Dictionary with all queued task IDs
        
    Example:
        POST /admin/trigger-full-sync
    """
    try:
        task_ids = trigger_full_sync()
        
        # Convert AsyncResult objects to strings
        task_ids_str = {
            key: str(value.id) if hasattr(value, 'id') else str(value)
            for key, value in task_ids.items()
        }
        
        return TaskResponse(
            message="Full sync initiated - multiple tasks queued",
            task_ids=task_ids_str
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger full sync: {str(e)}")


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a queued Celery task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status and result (if completed)
        
    Example:
        GET /admin/task-status/abc-123-def-456
    """
    from celery.result import AsyncResult
    from app.core.celery_app import celery_app
    
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        return {
            "task_id": task_id,
            "status": result.state,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {str(e)}")


@router.get("/worker-stats")
async def get_worker_stats():
    """
    Get Celery worker statistics.
    
    Shows active workers, queued tasks, and system health.
    
    Returns:
        Worker statistics
        
    Example:
        GET /admin/worker-stats
    """
    from app.core.celery_app import celery_app
    
    try:
        # Get active workers
        inspector = celery_app.control.inspect()
        
        active = inspector.active()
        reserved = inspector.reserved()
        stats = inspector.stats()
        
        return {
            "active_workers": list(active.keys()) if active else [],
            "active_tasks": sum(len(tasks) for tasks in active.values()) if active else 0,
            "reserved_tasks": sum(len(tasks) for tasks in reserved.values()) if reserved else 0,
            "worker_stats": stats
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Unable to fetch worker stats - workers may be offline"
        }
