from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardResponse, PLChartResponse
from app.services.dashboard_service import DashboardService

router = APIRouter()

@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete dashboard data for current user
    
    Returns overview cards, recent trades, and notifications
    """
    dashboard_service = DashboardService(db)
    
    # Get all dashboard data
    overview = await dashboard_service.get_dashboard_overview(current_user.id)
    recent_trades = await dashboard_service.get_recent_trades(current_user.id, limit=10)
    notifications = await dashboard_service.get_user_notifications(current_user.id, limit=5)
    
    return DashboardResponse(
        overview=overview,
        recent_trades=recent_trades,
        notifications=notifications
    )

@router.get("/pnl-chart", response_model=PLChartResponse)
async def get_pnl_chart(
    period: str = Query("7d", regex="^(24h|7d|30d|all)$"),
    group_by: Optional[str] = Query(None, regex="^(market|trader)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get P&L chart data
    
    - **period**: Time period (24h, 7d, 30d, all)
    - **group_by**: Optional grouping (market or trader)
    """
    dashboard_service = DashboardService(db)
    
    return await dashboard_service.get_pnl_chart_data(
        user_id=current_user.id,
        period=period,
        group_by=group_by
    )

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read"""
    dashboard_service = DashboardService(db)
    
    success = await dashboard_service.mark_notification_read(
        notification_id=notification_id,
        user_id=current_user.id
    )
    
    if not success:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user notifications"""
    dashboard_service = DashboardService(db)
    
    notifications = await dashboard_service.get_user_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit
    )
    
    return {"notifications": notifications}
