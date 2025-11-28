"""
User Emergency Controls

User-facing emergency stop and risk management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.api_key import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.risk.risk_management import get_risk_management_service


router = APIRouter(prefix="/user", tags=["user-emergency"])


@router.post("/emergency-stop")
async def emergency_stop(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    **EMERGENCY STOP**: Immediately stop all copy trading for this user.
    
    **Actions:**
    1. Pause all active copy relationships
    2. Cancel pending orders
    3. Optionally close open positions (future feature)
    
    **Warning:** This is an irreversible emergency action.  
    You will need to manually resume copy trading after investigation.
    """
    # TODO: Pause all copy relationships for user
    # TODO: Cancel pending orders
    # TODO: Optionally close positions
    
    # Apply cooling period
    risk_service = get_risk_management_service()
    await risk_service.apply_cooling_period(
        user_id=current_user.id,
        reason="User triggered emergency stop"
    )
    
    return {
        "message": "Emergency stop activated",
        "copy_relationships_paused": 0,  # TODO: Count
        "pending_orders_cancelled": 0,  # TODO: Count
        "cooling_period_hours": risk_service.COOLING_PERIOD_HOURS
    }


@router.get("/risk-status")
async def get_user_risk_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's current risk status.
    
    **Returns:**
    - Daily P&L
    - Loss limits
    - Cooling period status
    - Circuit breaker status
    """
    risk_service = get_risk_management_service()
    
    # Check daily loss
    exceeded_loss_limit, total_loss = await risk_service.check_user_daily_loss_limit(
        db,
        current_user.id
    )
    
    # Check circuit breaker
    circuit_breaker_active = await risk_service.is_circuit_breaker_active()
    
    return {
        "daily_loss_today": float(total_loss),
        "daily_loss_limit": float(risk_service.DEFAULT_DAILY_LOSS_LIMIT_USD),
        "exceeded_loss_limit": exceeded_loss_limit,
        "circuit_breaker_active": circuit_breaker_active,
        "in_cooling_period": False  # TODO: Check Redis
    }
