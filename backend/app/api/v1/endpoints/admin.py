"""
Admin Control Endpoints

Emergency controls and risk management admin APIs.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.models.api_key import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.risk.risk_management import (
    get_risk_management_service,
    CircuitBreakerReason
)


router = APIRouter(prefix="/admin", tags=["admin-controls"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CircuitBreakerTrigger(BaseModel):
    """Manual circuit breaker trigger"""
    reason: str
    details: Optional[str] = None


class PauseTraderRequest(BaseModel):
    """Pause trader request"""
    reason: str


# ============================================================================
# Admin Authentication
# ============================================================================

async def get_admin_user(current_user: User = Depends(get_current_user)):
    """Verify  user is admin"""
    # Check if user has admin role
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


# ============================================================================
# Circuit Breaker Controls
# ============================================================================

@router.post("/circuit-breaker/trigger")
async def trigger_circuit_breaker(
    request: CircuitBreakerTrigger,
    admin_user: User = Depends(get_admin_user)
):
    """
    Manually trigger circuit breaker to pause all copy trading.
    
    **Requires:** Admin access
    """
    risk_service = get_risk_management_service()
    
    await risk_service.trigger_circuit_breaker(
        reason=CircuitBreakerReason.MANUAL_TRIGGER,
        triggered_by=str(admin_user.id),
        details=request.details or request.reason
    )
    
    return {
        "message": "Circuit breaker triggered",
        "triggered_by": admin_user.email
    }


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    admin_user: User = Depends(get_admin_user)
):
    """
    Reset circuit breaker to resume operations.
    
    **Requires:** Admin access
    **Warning:** Ensure underlying issues are resolved before resetting
    """
    risk_service = get_risk_management_service()
    
    await risk_service.reset_circuit_breaker(
        reset_by=str(admin_user.id)
    )
    
    return {
        "message": "Circuit breaker reset",
        "reset_by": admin_user.email
    }


@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status(
    admin_user: User = Depends(get_admin_user)
):
    """Get current circuit breaker status"""
    risk_service = get_risk_management_service()
    
    is_active = await risk_service.is_circuit_breaker_active()
    
    return {
        "is_active": is_active
    }


# ============================================================================
# Trader Controls
# ============================================================================

@router.post("/pause-trader/{trader_address}")
async def pause_trader(
    trader_address: str,
    request: PauseTraderRequest,
    admin_user: User = Depends(get_admin_user)
):
    """
    Pause all copying of a specific trader.
    
    **Requires:** Admin access
    **Effect:** All active copy relationships for this trader will be paused
    """
    risk_service = get_risk_management_service()
    
    await risk_service.pause_trader(
        trader_address=trader_address,
        reason=request.reason,
        paused_by=str(admin_user.id)
    )
    
    return {
        "message": f"Trader {trader_address} paused",
        "reason": request.reason
    }


@router.post("/resume-trader/{trader_address}")
async def resume_trader(
    trader_address: str,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Resume copying of a paused trader"""
    risk_service = get_risk_management_service()
    
    # Remove from paused list
    if risk_service.redis:
        await risk_service.redis.hdel(
            risk_service.paused_traders_key,
            trader_address
        )
    
    return {
        "message": f"Trader {trader_address} resumed"
    }


# ============================================================================
# Dashboard Data
# ============================================================================

@router.get("/dashboard/risk-metrics")
async def get_risk_metrics(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get risk management metrics for admin dashboard.
    
    **Returns:**
    - Active circuit breakers
    - Paused traders
    - Users in cooling period
    - Recent risk events
    """
    risk_service = get_risk_management_service()
    
    # Get circuit breaker status
    is_circuit_breaker_active = await risk_service.is_circuit_breaker_active()
    
    # Check failure rate
    should_trigger, failure_rate = await risk_service.check_failure_rate(db)
    
    # Get paused traders (would query Redis)
    paused_traders_count = 0
    
    return {
        "circuit_breaker_active": is_circuit_breaker_active,
        "failure_rate_last_hour": f"{failure_rate * 100:.1f}%",
        "paused_traders": paused_traders_count,
        "users_in_cooling_period": 0,  # TODO: Count from Redis
        "recent_risk_events": []  # TODO: Query from audit log
    }
