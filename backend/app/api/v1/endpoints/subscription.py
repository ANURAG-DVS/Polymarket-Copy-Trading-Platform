"""
Subscription Endpoints

Manage user subscriptions, usage tracking, and upgrades.
"""

from typing import Optional
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.db.session import get_db
from app.models.api_key import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.subscription.subscription_service import (
    get_subscription_service,
    SubscriptionTier
)


router = APIRouter(prefix="/user/subscription", tags=["subscription"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SubscriptionResponse(BaseModel):
    """Current subscription details"""
    tier: str
    status: str  # active, cancelled, expired
    price_monthly: float
    started_at: datetime
    renews_at: Optional[datetime]
    
    # Limits
    max_copy_traders: Optional[int]
    max_monthly_volume_usd: Optional[float]
    max_api_calls_per_day: Optional[int]
    
    # Features
    features: list[str]


class UsageResponse(BaseModel):
    """Current usage statistics"""
    # Period
    period_start: datetime
    period_end: datetime
    
    # Usage
    copy_traders_count: int
    monthly_volume_usd: float
    api_calls_today: int
    
    # Limits
    max_copy_traders: Optional[int]
    max_monthly_volume_usd: Optional[float]
    max_api_calls_per_day: Optional[int]
    
    # Percentages
    copy_traders_usage_percent: float
    volume_usage_percent: float
    api_calls_usage_percent: float
    
    # Warnings
    warnings: list[str] = []


class UpgradeRequest(BaseModel):
    """Subscription upgrade request"""
    target_tier: str
    payment_method_id: Optional[str] = None  # Stripe payment method


# ============================================================================
# Helper Functions
# ============================================================================

async def get_monthly_usage(
    db: AsyncSession,
    user_id: int
) -> dict:
    """Get user's current month usage"""
    # Calculate period
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # In production, query user_usage table
    # For now, return mock data
    return {
        "copy_traders_count": 0,
        "monthly_volume_usd": Decimal('0'),
        "api_calls_today": 0,
        "period_start": period_start,
        "period_end": period_start + timedelta(days=30)
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user)
):
    """
    Get current subscription details.
    
    **Returns:**
    - Current tier and limits
    - Renewal date
    - Available features
    """
    subscription_service = get_subscription_service()
    
    # Get user's tier (from database in production)
    tier = SubscriptionTier(current_user.subscription_tier if hasattr(current_user, 'subscription_tier') else 'free')
    limits = subscription_service.get_tier_limits(tier)
    price = subscription_service.get_tier_price(tier)
    
    # Calculate renewal date
    started_at = current_user.created_at
    renews_at = None
    if tier != SubscriptionTier.FREE:
        # Monthly renewal
        renews_at = started_at + timedelta(days=30)
    
    return SubscriptionResponse(
        tier=tier.value,
        status="active",
        price_monthly=float(price),
        started_at=started_at,
        renews_at=renews_at,
        max_copy_traders=limits.max_copy_traders,
        max_monthly_volume_usd=float(limits.max_monthly_volume_usd) if limits.max_monthly_volume_usd else None,
        max_api_calls_per_day=limits.max_api_calls_per_day,
        features=limits.features
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current month usage statistics.
    
    **Returns:**
    - Copy traders count
    - Monthly volume
    - API calls
    - Usage percentages
    - Limit warnings
    """
    subscription_service = get_subscription_service()
    
    # Get tier and limits
    tier = SubscriptionTier(current_user.subscription_tier if hasattr(current_user, 'subscription_tier') else 'free')
    limits = subscription_service.get_tier_limits(tier)
    
    # Get usage
    usage = await get_monthly_usage(db, current_user.id)
    
    # Calculate percentages
    def calc_percent(current, maximum):
        if maximum is None:
            return 0  # Unlimited
        return (current / maximum * 100) if maximum > 0 else 0
    
    copy_percent = calc_percent(
        usage['copy_traders_count'],
        limits.max_copy_traders
    )
    
    volume_percent = calc_percent(
        float(usage['monthly_volume_usd']),
        float(limits.max_monthly_volume_usd) if limits.max_monthly_volume_usd else None
    )
    
    api_percent = calc_percent(
        usage['api_calls_today'],
        limits.max_api_calls_per_day
    )
    
    # Generate warnings
    warnings = []
    if copy_percent >= 80:
        warnings.append(f"Copy traders: {copy_percent:.1f}% of limit used")
    if volume_percent >= 80:
        warnings.append(f"Monthly volume: {volume_percent:.1f}% of limit used")
    if api_percent >= 80:
        warnings.append(f"API calls: {api_percent:.1f}% of daily limit used")
    
    return UsageResponse(
        period_start=usage['period_start'],
        period_end=usage['period_end'],
        copy_traders_count=usage['copy_traders_count'],
        monthly_volume_usd=float(usage['monthly_volume_usd']),
        api_calls_today=usage['api_calls_today'],
        max_copy_traders=limits.max_copy_traders,
        max_monthly_volume_usd=float(limits.max_monthly_volume_usd) if limits.max_monthly_volume_usd else None,
        max_api_calls_per_day=limits.max_api_calls_per_day,
        copy_traders_usage_percent=copy_percent,
        volume_usage_percent=volume_percent,
        api_calls_usage_percent=api_percent,
        warnings=warnings
    )


@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upgrade subscription tier.
    
    **Payment Integration Placeholder:**
    This endpoint will integrate with Stripe/PayPal in Phase 4.
    Currently returns mock success for testing.
    
    **Input:**
    - target_tier: "pro" or "enterprise"
    - payment_method_id: Payment method (optional for now)
    
    **Returns:**
    - Subscription details
    - Payment confirmation (mock)
    """
    subscription_service = get_subscription_service()
    
    # Validate tier
    try:
        target_tier = SubscriptionTier(request.target_tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.target_tier}"
        )
    
    # Get current tier
    current_tier = SubscriptionTier(
        current_user.subscription_tier 
        if hasattr(current_user, 'subscription_tier') 
        else 'free'
    )
    
    # Validate upgrade path
    if target_tier == current_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already on this tier"
        )
    
    if target_tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot downgrade to free tier via this endpoint"
        )
    
    # Get pricing
    price = subscription_service.get_tier_price(target_tier)
    
    # TODO: Phase 4 - Integrate with Stripe
    # stripe_response = await process_stripe_subscription(
    #     user_id=current_user.id,
    #     tier=target_tier,
    #     payment_method_id=request.payment_method_id
    # )
    
    # Mock payment success
    payment_success = True
    
    if payment_success:
        # Update user's subscription
        current_user.subscription_tier = target_tier.value
        current_user.subscription_status = "active"
        current_user.subscription_started_at = datetime.utcnow()
        await db.commit()
        
        return {
            "success": True,
            "message": f"Upgraded to {target_tier.value} tier",
            "tier": target_tier.value,
            "price_monthly": float(price),
            "next_billing_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "payment_method": "mock_payment_method"  # Placeholder
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment failed"
        )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel subscription (will downgrade to free at end of billing period).
    
    **Note:** Subscription remains active until end of paid period.
    """
    # TODO: Phase 4 - Cancel Stripe subscription
    
    current_user.subscription_status = "cancelled"
    await db.commit()
    
    return {
        "message": "Subscription cancelled. Access continues until end of billing period.",
        "access_until": (datetime.utcnow() + timedelta(days=30)).isoformat()
    }


@router.get("/plans")
async def list_subscription_plans():
    """
    List all available subscription plans.
    
    **Returns:**
    - All tiers with pricing and features
    """
    subscription_service = get_subscription_service()
    
    plans = []
    for tier in SubscriptionTier:
        limits = subscription_service.get_tier_limits(tier)
        price = subscription_service.get_tier_price(tier)
        
        plans.append({
            "tier": tier.value,
            "name": tier.value.title(),
            "price_monthly": float(price),
            "limits": {
                "max_copy_traders": limits.max_copy_traders,
                "max_monthly_volume_usd": float(limits.max_monthly_volume_usd) if limits.max_monthly_volume_usd else None,
                "max_api_calls_per_day": limits.max_api_calls_per_day
            },
            "features": limits.features
        })
    
    return {"plans": plans}
