from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.models.user import User
from app.models.user_preferences import UserPreferences, BillingHistory
from app.models.copy_relationship import CopyRelationship, RelationshipStatus
from app.core.security import verify_password, get_password_hash
from app.core.config import settings
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class SettingsService:
    """Service for user settings management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def update_profile(
        self,
        user_id: int,
        username: Optional[str] = None,
        email: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> User:
        """Update user profile"""
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if username:
            # Check if username is taken
            existing = await self.db.execute(
                select(User).where(
                    and_(
                        User.username == username,
                        User.id != user_id
                    )
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            user.username = username
        
        if email:
            # Check if email is taken
            existing = await self.db.execute(
                select(User).where(
                    and_(
                        User.email == email,
                        User.id != user_id
                    )
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already taken"
                )
            user.email = email
        
        if full_name:
            user.full_name = full_name
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Updated profile for user {user_id}")
        return user
    
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change user password"""
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        
        logger.info(f"Password changed for user {user_id}")
        return True
    
    async def save_polymarket_keys(
        self,
        user_id: int,
        api_key: str,
        api_secret: str
    ) -> bool:
        """Save encrypted Polymarket API keys"""
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Encrypt keys
        fernet = Fernet(settings.MASTER_ENCRYPTION_KEY.encode())
        encrypted_key = fernet.encrypt(api_key.encode()).decode()
        encrypted_secret = fernet.encrypt(api_secret.encode()).decode()
        
        user.polymarket_api_key = encrypted_key
        user.polymarket_api_secret = encrypted_secret
        
        await self.db.commit()
        
        logger.info(f"Saved Polymarket keys for user {user_id}")
        return True
    
    async def test_polymarket_connection(self, user_id: int) -> bool:
        """Test Polymarket API connection"""
        # TODO: Implement actual API test
        # For now, just check if keys exist
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        return bool(user.polymarket_api_key and user.polymarket_api_secret)
    
    async def revoke_polymarket_keys(self, user_id: int) -> bool:
        """Remove Polymarket API keys"""
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.polymarket_api_key = None
        user.polymarket_api_secret = None
        
        await self.db.commit()
        
        logger.info(f"Revoked Polymarket keys for user {user_id}")
        return True
    
    async def get_or_create_preferences(self, user_id: int) -> UserPreferences:
        """Get or create user preferences"""
        
        result = await self.db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        prefs = result.scalars().first()
        
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            self.db.add(prefs)
            await self.db.commit()
            await self.db.refresh(prefs)
        
        return prefs
    
    async def update_preferences(
        self,
        user_id: int,
        **kwargs
    ) -> UserPreferences:
        """Update user preferences"""
        
        prefs = await self.get_or_create_preferences(user_id)
        
        for key, value in kwargs.items():
            if value is not None and hasattr(prefs, key):
                setattr(prefs, key, value)
        
        await self.db.commit()
        await self.db.refresh(prefs)
        
        logger.info(f"Updated preferences for user {user_id}")
        return prefs
    
    async def get_subscription_usage(self, user_id: int) -> dict:
        """Get subscription usage stats"""
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        # Get active copy relationships count
        copies_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    CopyRelationship.user_id == user_id,
                    CopyRelationship.status == RelationshipStatus.ACTIVE
                )
            )
        )
        current_traders = copies_result.scalar()
        
        # Define tier limits
        tier_limits = {
            "free": {"max_traders": 5, "max_volume": 5000},
            "pro": {"max_traders": 25, "max_volume": 25000},
            "enterprise": {"max_traders": 999, "max_volume": None}
        }
        
        tier = user.subscription_tier.value
        limits = tier_limits.get(tier, tier_limits["free"])
        
        # Get monthly volume (simplified - would need to sum from trades)
        current_monthly_volume = 0  # TODO: Calculate from trades
        
        return {
            "current_tier": tier,
            "max_traders": limits["max_traders"],
            "current_traders": current_traders,
            "max_monthly_volume": limits["max_volume"],
            "current_monthly_volume": current_monthly_volume
        }
    
    async def get_billing_history(self, user_id: int, limit: int = 10):
        """Get billing history"""
        
        result = await self.db.execute(
            select(BillingHistory)
            .where(BillingHistory.user_id == user_id)
            .order_by(BillingHistory.created_at.desc())
            .limit(limit)
        )
        
        return result.scalars().all()
    
    async def delete_account(self, user_id: int, password: str) -> bool:
        """Delete user account"""
        
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect password"
            )
        
        # Soft delete - just deactivate
        user.is_active = False
        await self.db.commit()
        
        logger.info(f"Deleted account for user {user_id}")
        return True
