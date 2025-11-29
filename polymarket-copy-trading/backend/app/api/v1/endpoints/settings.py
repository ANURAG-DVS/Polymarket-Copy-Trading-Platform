from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.positions import (
    ProfileUpdateRequest,
    ChangePasswordRequest,
    PolymarketKeysRequest,
    PolymarketKeysStatus,
    NotificationPreferencesRequest,
    TradingPreferencesRequest,
    UserPreferencesResponse,
    SubscriptionUsage,
    BillingHistoryResponse
)
from app.schemas.user import UserResponse
from app.services.settings_service import SettingsService

router = APIRouter()

# ========== PROFILE ==========

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile"""
    
    settings_service = SettingsService(db)
    
    user = await settings_service.update_profile(
        user_id=current_user.id,
        username=request.username,
        email=request.email,
        full_name=request.full_name
    )
    
    return UserResponse.from_orm(user)

@router.post("/profile/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    
    settings_service = SettingsService(db)
    
    await settings_service.change_password(
        user_id=current_user.id,
        current_password=request.current_password,
        new_password=request.new_password
    )
    
    return {"message": "Password changed successfully"}

@router.delete("/profile/delete")
async def delete_account(
    password: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user account"""
    
    settings_service = SettingsService(db)
    
    await settings_service.delete_account(
        user_id=current_user.id,
        password=password
    )
    
    return {"message": "Account deleted successfully"}

# ========== POLYMARKET KEYS ==========

@router.post("/polymarket-keys")
async def save_polymarket_keys(
    request: PolymarketKeysRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save Polymarket API keys"""
    
    settings_service = SettingsService(db)
    
    await settings_service.save_polymarket_keys(
        user_id=current_user.id,
        api_key=request.api_key,
        api_secret=request.api_secret
    )
    
    return {"message": "Polymarket keys saved successfully"}

@router.get("/polymarket-keys/status", response_model=PolymarketKeysStatus)
async def get_polymarket_keys_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get Polymarket keys status"""
    
    is_configured = bool(current_user.polymarket_api_key)
    
    return PolymarketKeysStatus(
        is_configured=is_configured,
        last_tested=None,  # TODO: Track last test time
        is_valid=is_configured
    )

@router.post("/polymarket-keys/test")
async def test_polymarket_connection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test Polymarket API connection"""
    
    settings_service = SettingsService(db)
    
    is_valid = await settings_service.test_polymarket_connection(current_user.id)
    
    return {
        "is_valid": is_valid,
        "message": "Connection successful" if is_valid else "Connection failed"
    }

@router.delete("/polymarket-keys")
async def revoke_polymarket_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke Polymarket API keys"""
    
    settings_service = SettingsService(db)
    
    await settings_service.revoke_polymarket_keys(current_user.id)
    
    return {"message": "Polymarket keys revoked successfully"}

# ========== PREFERENCES ==========

@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user preferences"""
    
    settings_service = SettingsService(db)
    
    prefs = await settings_service.get_or_create_preferences(current_user.id)
    
    return UserPreferencesResponse.from_orm(prefs)

@router.put("/preferences/notifications")
async def update_notification_preferences(
    request: NotificationPreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update notification preferences"""
    
    settings_service = SettingsService(db)
    
    prefs = await settings_service.update_preferences(
        user_id=current_user.id,
        **request.dict(exclude_unset=True)
    )
    
    return {"message": "Notification preferences updated", "preferences": UserPreferencesResponse.from_orm(prefs)}

@router.put("/preferences/trading")
async def update_trading_preferences(
    request: TradingPreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update trading preferences"""
    
    settings_service = SettingsService(db)
    
    prefs = await settings_service.update_preferences(
        user_id=current_user.id,
        **request.dict(exclude_unset=True)
    )
    
    return {"message": "Trading preferences updated", "preferences": UserPreferencesResponse.from_orm(prefs)}

# ========== SUBSCRIPTION ==========

@router.get("/subscription/usage", response_model=SubscriptionUsage)
async def get_subscription_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get subscription usage stats"""
    
    settings_service = SettingsService(db)
    
    usage = await settings_service.get_subscription_usage(current_user.id)
    
    return SubscriptionUsage(**usage)

@router.get("/subscription/billing-history")
async def get_billing_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get billing history"""
    
    settings_service = SettingsService(db)
    
    history = await settings_service.get_billing_history(current_user.id, limit)
    
    return {
        "billing_history": [BillingHistoryResponse.from_orm(h) for h in history]
    }
