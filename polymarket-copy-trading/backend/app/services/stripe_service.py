import stripe
from typing import Optional, Dict, Any
from app.core.config import settings
from app.models.user import User, SubscriptionTier
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    """Service for Stripe payment operations"""
    
    # Subscription price IDs (set these in Stripe Dashboard)
    PRICE_IDS = {
        SubscriptionTier.PRO: settings.STRIPE_PRO_PRICE_ID,
        SubscriptionTier.ENTERPRISE: settings.STRIPE_ENTERPRISE_PRICE_ID,
    }
    
    @staticmethod
    async def create_customer(user: User) -> str:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name or user.username,
                metadata={
                    'user_id': str(user.id),
                    'username': user.username
                }
            )
            
            logger.info(f"Created Stripe customer: {customer.id} for user {user.id}")
            return customer.id
        
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise
    
    @staticmethod
    async def create_checkout_session(
        user: User,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session for subscription"""
        
        # Get or create Stripe customer
        if not user.stripe_customer_id:
            customer_id = await StripeService.create_customer(user)
            user.stripe_customer_id = customer_id
        else:
            customer_id = user.stripe_customer_id
        
        # Get price ID for tier
        price_id = StripeService.PRICE_IDS.get(tier)
        if not price_id:
            raise ValueError(f"No price ID configured for tier: {tier}")
        
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode='subscription',
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user.id),
                    'tier': tier.value
                },
                subscription_data={
                    'metadata': {
                        'user_id': str(user.id),
                        'tier': tier.value
                    }
                },
                allow_promotion_codes=True,
            )
            
            logger.info(f"Created checkout session: {session.id} for user {user.id}")
            return {
                'session_id': session.id,
                'url': session.url
            }
        
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise
    
    @staticmethod
    async def create_portal_session(
        user: User,
        return_url: str
    ) -> Dict[str, str]:
        """Create a Stripe customer portal session"""
        
        if not user.stripe_customer_id:
            raise ValueError("User does not have a Stripe customer ID")
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url,
            )
            
            logger.info(f"Created portal session for user {user.id}")
            return {'url': session.url}
        
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            raise
    
    @staticmethod
    async def handle_checkout_completed(
        session: Dict[str, Any],
        db: AsyncSession
    ):
        """Handle successful checkout completion"""
        
        user_id = int(session['metadata']['user_id'])
        tier = SubscriptionTier(session['metadata']['tier'])
        subscription_id = session['subscription']
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found: {user_id}")
            return
        
        # Update subscription
        user.subscription_tier = tier
        user.stripe_subscription_id = subscription_id
        user.subscription_status = 'active'
        
        await db.commit()
        
        logger.info(f"Updated user {user_id} to tier {tier}")
        
        # TODO: Send confirmation email
        # await send_subscription_confirmation_email(user)
    
    @staticmethod
    async def handle_subscription_updated(
        subscription: Dict[str, Any],
        db: AsyncSession
    ):
        """Handle subscription update"""
        
        user_id = int(subscription['metadata']['user_id'])
        status = subscription['status']
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found: {user_id}")
            return
        
        # Update status
        user.subscription_status = status
        
        # If canceled or past_due, downgrade to free
        if status in ['canceled', 'past_due', 'unpaid']:
            user.subscription_tier = SubscriptionTier.FREE
            logger.warning(f"Downgraded user {user_id} to FREE due to status: {status}")
        
        await db.commit()
    
    @staticmethod
    async def handle_subscription_deleted(
        subscription: Dict[str, Any],
        db: AsyncSession
    ):
        """Handle subscription deletion/cancellation"""
        
        user_id = int(subscription['metadata']['user_id'])
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found: {user_id}")
            return
        
        # Downgrade to free
        user.subscription_tier = SubscriptionTier.FREE
        user.subscription_status = 'canceled'
        user.stripe_subscription_id = None
        
        await db.commit()
        
        logger.info(f"Canceled subscription for user {user_id}")
        
        # TODO: Send cancellation email
        # await send_subscription_canceled_email(user)
    
    @staticmethod
    async def handle_payment_failed(
        invoice: Dict[str, Any],
        db: AsyncSession
    ):
        """Handle failed payment"""
        
        customer_id = invoice['customer']
        
        # Find user by customer ID
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found for customer: {customer_id}")
            return
        
        # Update status
        user.subscription_status = 'past_due'
        
        await db.commit()
        
        logger.warning(f"Payment failed for user {user.id}")
        
        # TODO: Send payment failed email
        # await send_payment_failed_email(user, invoice)
    
    @staticmethod
    def construct_webhook_event(
        payload: bytes,
        sig_header: str,
        webhook_secret: str
    ):
        """Construct and verify webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise
