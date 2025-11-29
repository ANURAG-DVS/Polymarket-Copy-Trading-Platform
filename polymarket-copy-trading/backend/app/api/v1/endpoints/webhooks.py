from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.stripe_service import StripeService
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Stripe webhook events"""
    
    # Get payload and signature
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    
    # Verify and construct event
    try:
        event = StripeService.construct_webhook_event(
            payload=payload,
            sig_header=sig_header,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle different event types
    event_type = event['type']
    data = event['data']['object']
    
    logger.info(f"Received webhook event: {event_type}")
    
    try:
        if event_type == 'checkout.session.completed':
            # Payment successful, activate subscription
            await StripeService.handle_checkout_completed(data, db)
        
        elif event_type == 'customer.subscription.updated':
            # Subscription updated (renewed, changed, etc.)
            await StripeService.handle_subscription_updated(data, db)
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription canceled
            await StripeService.handle_subscription_deleted(data, db)
        
        elif event_type == 'invoice.payment_failed':
            # Payment failed, mark as past_due
            await StripeService.handle_payment_failed(data, db)
        
        elif event_type == 'invoice.payment_succeeded':
            # Successful renewal payment
            logger.info(f"Payment succeeded for invoice: {data['id']}")
        
        else:
            logger.warning(f"Unhandled event type: {event_type}")
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Return 200 to Stripe to avoid retries for unrecoverable errors
        # But log the error for investigation
    
    return {"status": "success"}
