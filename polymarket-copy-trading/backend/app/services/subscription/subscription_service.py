"""
Subscription Service

Manages subscription tiers, limits, and usage tracking.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from loguru import logger


class SubscriptionTier(str, Enum):
    """Subscription tier levels"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class TierLimits:
    """Limits for a subscription tier"""
    max_copy_traders: Optional[int]  # None = unlimited
    max_monthly_volume_usd: Optional[Decimal]  # None = unlimited
    max_api_calls_per_day: Optional[int]
    features: list[str]


class SubscriptionService:
    """
    Manage subscriptions and enforce usage limits.
    
    Tiers:
    - Free: 1 trader, $100/month volume
    - Pro: 5 traders, $5,000/month volume
    - Enterprise: Unlimited
    """
    
    # Tier configurations
    TIER_LIMITS = {
        SubscriptionTier.FREE: TierLimits(
            max_copy_traders=1,
            max_monthly_volume_usd=Decimal('100'),
            max_api_calls_per_day=1000,
            features=['basic_analytics', 'email_notifications']
        ),
        SubscriptionTier.PRO: TierLimits(
            max_copy_traders=5,
            max_monthly_volume_usd=Decimal('5000'),
            max_api_calls_per_day=10000,
            features=[
                'basic_analytics',
                'advanced_analytics',
                'email_notifications',
                'telegram_notifications',
                'auto_close_trades'
            ]
        ),
        SubscriptionTier.ENTERPRISE: TierLimits(
            max_copy_traders=None,  # Unlimited
            max_monthly_volume_usd=None,  # Unlimited
            max_api_calls_per_day=None,  # Unlimited
            features=[
                'basic_analytics',
                'advanced_analytics',
                'email_notifications',
                'telegram_notifications',
                'auto_close_trades',
                'priority_support',
                'custom_integrations',
                'api_access'
            ]
        )
    }
    
    # Pricing (monthly)
    TIER_PRICING = {
        SubscriptionTier.FREE: Decimal('0'),
        SubscriptionTier.PRO: Decimal('29.99'),
        SubscriptionTier.ENTERPRISE: Decimal('199.99')
    }
    
    def __init__(self):
        """Initialize subscription service"""
        logger.info("SubscriptionService initialized")
    
    def get_tier_limits(self, tier: SubscriptionTier) -> TierLimits:
        """Get limits for a tier"""
        return self.TIER_LIMITS[tier]
    
    def get_tier_price(self, tier: SubscriptionTier) -> Decimal:
        """Get monthly price for a tier"""
        return self.TIER_PRICING[tier]
    
    def check_copy_trader_limit(
        self,
        tier: SubscriptionTier,
        current_count: int
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can add another copy trader.
        
        Returns:
            (allowed, message)
        """
        limits = self.get_tier_limits(tier)
        
        if limits.max_copy_traders is None:
            return True, None
        
        if current_count >= limits.max_copy_traders:
            return False, (
                f"Copy trader limit reached ({limits.max_copy_traders}). "
                f"Upgrade to {'Pro' if tier == SubscriptionTier.FREE else 'Enterprise'} "
                f"for more traders."
            )
        
        # Warn when close to limit
        if current_count == limits.max_copy_traders - 1:
            return True, f"Warning: 1 copy trader slot remaining. Consider upgrading."
        
        return True, None
    
    def check_volume_limit(
        self,
        tier: SubscriptionTier,
        current_volume: Decimal,
        trade_amount: Decimal
    ) -> tuple[bool, Optional[str]]:
        """
        Check if trade would exceed monthly volume limit.
        
        Returns:
            (allowed, message)
        """
        limits = self.get_tier_limits(tier)
        
        if limits.max_monthly_volume_usd is None:
            return True, None
        
        new_volume = current_volume + trade_amount
        
        if new_volume > limits.max_monthly_volume_usd:
            return False, (
                f"Monthly volume limit exceeded. "
                f"Limit: ${limits.max_monthly_volume_usd}, "
                f"Current: ${current_volume}, "
                f"Trade: ${trade_amount}. "
                f"Upgrade to {'Pro' if tier == SubscriptionTier.FREE else 'Enterprise'}."
            )
        
        # Warn at 80% usage
        usage_percent = (new_volume / limits.max_monthly_volume_usd) * 100
        if usage_percent >= 80:
            remaining = limits.max_monthly_volume_usd - new_volume
            return True, (
                f"Warning: {usage_percent:.1f}% of monthly volume used. "
                f"${remaining} remaining."
            )
        
        return True, None
    
    def check_feature_access(
        self,
        tier: SubscriptionTier,
        feature: str
    ) -> bool:
        """Check if tier has access to a feature"""
        limits = self.get_tier_limits(tier)
        return feature in limits.features
    
    def get_upgrade_suggestion(
        self,
        current_tier: SubscriptionTier
    ) -> Optional[Dict[str, Any]]:
        """Get upgrade suggestion based on current tier"""
        if current_tier == SubscriptionTier.FREE:
            return {
                "suggested_tier": SubscriptionTier.PRO,
                "price": float(self.TIER_PRICING[SubscriptionTier.PRO]),
                "benefits": [
                    "Copy up to 5 traders (vs 1)",
                    "$5,000 monthly volume (vs $100)",
                    "Advanced analytics",
                    "Telegram notifications",
                    "Auto-close trades"
                ]
            }
        elif current_tier == SubscriptionTier.PRO:
            return {
                "suggested_tier": SubscriptionTier.ENTERPRISE,
                "price": float(self.TIER_PRICING[SubscriptionTier.ENTERPRISE]),
                "benefits": [
                    "Unlimited copy traders",
                    "Unlimited volume",
                    "Priority support",
                    "Custom integrations",
                    "API access"
                ]
            }
        
        return None  # Already on highest tier


# Singleton instance
_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get singleton instance"""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
