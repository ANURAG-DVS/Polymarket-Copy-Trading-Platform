from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.services.stripe_service import StripeService
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class CheckoutRequest(BaseModel):
    tier: SubscriptionTier
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class CheckoutResponse(BaseModel):
    session_id: str
    url: str

class PortalResponse(BaseModel):
    url: str

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe checkout session for subscription upgrade"""
    
    # Validate tier
    if request.tier == SubscriptionTier.FREE:
        raise HTTPException(status_code=400, detail="Cannot checkout for free tier")
    
    if current_user.subscription_tier == request.tier:
        raise HTTPException(status_code=400, detail="Already subscribed to this tier")
    
    # Set default URLs
    success_url = request.success_url or f"{settings.FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = request.cancel_url or f"{settings.FRONTEND_URL}/subscription/canceled"
    
    try:
        session_data = await StripeService.create_checkout_session(
            user=current_user,
            tier=request.tier,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return CheckoutResponse(**session_data)
    
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    current_user: User = Depends(get_current_user),
    return_url: Optional[str] = None
):
    """Create a Stripe customer portal session for managing subscription"""
    
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No active subscription to manage"
        )
    
    # Set default return URL
    return_url = return_url or f"{settings.FRONTEND_URL}/settings/billing"
    
    try:
        portal_data = await StripeService.create_portal_session(
            user=current_user,
            return_url=return_url
        )
        
        return PortalResponse(**portal_data)
    
    except Exception as e:
        logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")

@router.get("/status")
async def get_subscription_status(
    current_user: User = Depends(get_current_user)
):
    """Get current subscription status"""
    
    return {
        "tier": current_user.subscription_tier,
        "status": current_user.subscription_status,
        "stripe_customer_id": current_user.stripe_customer_id,
        "stripe_subscription_id": current_user.stripe_subscription_id
    }
