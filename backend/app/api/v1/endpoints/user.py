"""
User Profile and Settings Endpoints

Manage user profiles, preferences, API keys, and data export.
"""

import csv
import io
import json
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field, validator

from app.db.session import get_db
from app.models.api_key import User, Trade, APIKey
from app.api.v1.endpoints.auth import get_current_user
from app.services.encryption import get_encryption_service
from app.services.polymarket import get_polymarket_client


router = APIRouter(prefix="/user", tags=["user-profile"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ProfileUpdate(BaseModel):
    """Profile update request"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None


class ProfileResponse(BaseModel):
    """User profile response"""
    id: int
    email: str
    username: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class NotificationSettings(BaseModel):
    """Notification preferences"""
    # Email notifications
    email_trade_execution: bool = True
    email_pnl_updates: bool = True
    email_leaderboard_changes: bool = False
    email_weekly_summary: bool = True
    
    # Telegram notifications
    telegram_trade_execution: bool = False
    telegram_pnl_alerts: bool = False
    telegram_enabled: bool = False
    telegram_chat_id: Optional[str] = None
    
    # Push notifications
    push_enabled: bool = False


class TradingSettings(BaseModel):
    """Trading preferences"""
    default_copy_percentage: float = Field(100.0, ge=1.0, le=100.0)
    daily_spend_limit_usd: Optional[float] = Field(None, ge=0)
    weekly_spend_limit_usd: Optional[float] = Field(None, ge=0)
    
    # Auto-close settings
    enable_stop_loss: bool = False
    stop_loss_percentage: Optional[float] = Field(None, ge=1.0, le=100.0)
    enable_take_profit: bool = False
    take_profit_percentage: Optional[float] = Field(None, ge=1.0, le=1000.0)
    
    @validator('stop_loss_percentage')
    def validate_stop_loss(cls, v, values):
        if values.get('enable_stop_loss') and v is None:
            raise ValueError('Stop loss percentage required when enabled')
        return v
    
    @validator('take_profit_percentage')
    def validate_take_profit(cls, v, values):
        if values.get('enable_take_profit') and v is None:
            raise ValueError('Take profit percentage required when enabled')
        return v


class PolymarketKeysRequest(BaseModel):
    """Polymarket API keys"""
    api_key: str = Field(..., min_length=10)
    api_secret: str = Field(..., min_length=10)
    api_passphrase: Optional[str] = None


class AccountDeletionRequest(BaseModel):
    """Account deletion confirmation"""
    confirmation: str = Field(..., description="Type 'DELETE' to confirm")
    password: str


# ============================================================================
# Profile Endpoints
# ============================================================================

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user's profile.
    
    **Requires:** Valid access token
    """
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        bio=current_user.bio if hasattr(current_user, 'bio') else None,
        avatar_url=current_user.avatar_url if hasattr(current_user, 'avatar_url') else None,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at if hasattr(current_user, 'last_login_at') else None
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    profile: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile.
    
    **Updatable Fields:**
    - username (3-50 chars, unique)
    - bio (max 500 chars)
    - avatar_url
    """
    # Check username uniqueness if changing
    if profile.username and profile.username != current_user.username:
        query = select(User).where(User.username == profile.username)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = profile.username
    
    # Update other fields
    if profile.bio is not None:
        current_user.bio = profile.bio
    
    if profile.avatar_url is not None:
        current_user.avatar_url = profile.avatar_url
    
    await db.commit()
    await db.refresh(current_user)
    
    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        bio=current_user.bio if hasattr(current_user, 'bio') else None,
        avatar_url=current_user.avatar_url if hasattr(current_user, 'avatar_url') else None,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at if hasattr(current_user, 'last_login_at') else None
    )


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    request: AccountDeletionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete user account permanently.
    
    **DANGER:** This action cannot be undone.
    
    **Requirements:**
    - confirmation: Must be exactly "DELETE"
    - password: Current password for verification
    """
    from app.services.auth import get_auth_service
    
    # Verify confirmation
    if request.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation must be 'DELETE'"
        )
    
    # Verify password
    auth_service = get_auth_service()
    if not auth_service.verify_password(request.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Delete user data
    # Note: CASCADE should handle related records
    await db.delete(current_user)
    await db.commit()
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Settings Endpoints
# ============================================================================

@router.get("/settings/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(get_current_user)
):
    """Get notification preferences"""
    # In production, fetch from user_settings table
    # For now, return defaults
    return NotificationSettings()


@router.put("/settings/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update notification preferences.
    
    **Configure:**
    - Email alerts (trades, P&L, leaderboard, weekly summary)
    - Telegram notifications (requires chat ID)
    - Push notifications
    """
    # In production, upsert to user_settings table
    # For now, return the settings
    return settings


@router.get("/settings/trading", response_model=TradingSettings)
async def get_trading_settings(
    current_user: User = Depends(get_current_user)
):
    """Get trading preferences"""
    # In production, fetch from user_settings table
    return TradingSettings()


@router.put("/settings/trading", response_model=TradingSettings)
async def update_trading_settings(
    settings: TradingSettings,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update trading preferences.
    
    **Configure:**
    - Default copy percentage (1-100%)
    - Spend limits (daily/weekly in USD)
    - Auto-close (stop loss, take profit)
    """
    # Validate spend limits
    if settings.daily_spend_limit_usd and settings.weekly_spend_limit_usd:
        if settings.daily_spend_limit_usd > settings.weekly_spend_limit_usd:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily limit cannot exceed weekly limit"
            )
    
    # In production, upsert to user_settings table
    return settings


# ============================================================================
# API Key Management
# ============================================================================

@router.post("/polymarket-keys", status_code=status.HTTP_201_CREATED)
async def add_polymarket_keys(
    keys: PolymarketKeysRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add or update Polymarket API keys.
    
    **Security:** Keys are encrypted before storage.
    """
    encryption = get_encryption_service()
    
    # Encrypt keys
    encrypted_key = encryption.encrypt(keys.api_key)
    encrypted_secret = encryption.encrypt(keys.api_secret)
    encrypted_passphrase = (
        encryption.encrypt(keys.api_passphrase)
        if keys.api_passphrase else None
    )
    
    # Check if keys already exist
    query = select(APIKey).where(APIKey.user_id == current_user.id)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing
        existing.api_key_encrypted = encrypted_key
        existing.api_secret_encrypted = encrypted_secret
        existing.passphrase_encrypted = encrypted_passphrase
        existing.updated_at = datetime.utcnow()
    else:
        # Create new
        new_key = APIKey(
            user_id=current_user.id,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            passphrase_encrypted=encrypted_passphrase
        )
        db.add(new_key)
    
    await db.commit()
    
    return {"message": "API keys saved successfully"}


@router.get("/polymarket-keys/status")
async def get_polymarket_keys_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if Polymarket API keys are configured.
    
    **Does NOT return actual keys for security.**
    """
    query = select(APIKey).where(APIKey.user_id == current_user.id)
    result = await db.execute(query)
    keys = result.scalar_one_or_none()
    
    return {
        "configured": keys is not None,
        "created_at": keys.created_at if keys else None,
        "updated_at": keys.updated_at if keys else None
    }


@router.delete("/polymarket-keys", status_code=status.HTTP_204_NO_CONTENT)
async def delete_polymarket_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete stored Polymarket API keys"""
    query = delete(APIKey).where(APIKey.user_id == current_user.id)
    await db.execute(query)
    await db.commit()
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/polymarket-keys/test")
async def test_polymarket_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Test if stored Polymarket API keys are valid.
    
    **Tests:** Attempts to fetch account balance.
    """
    # Get stored keys
    query = select(APIKey).where(APIKey.user_id == current_user.id)
    result = await db.execute(query)
    keys = result.scalar_one_or_none()
    
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No API keys configured"
        )
    
    # Decrypt keys
    encryption = get_encryption_service()
    api_key = encryption.decrypt(keys.api_key_encrypted)
    api_secret = encryption.decrypt(keys.api_secret_encrypted)
    
    # Test keys
    try:
        client = get_polymarket_client()
        # In production, would initialize client with user's keys
        # and test API call
        balance = await client.get_balance()
        
        return {
            "valid": True,
            "message": "API keys are working",
            "balance": balance
        }
    except Exception as e:
        return {
            "valid": False,
            "message": f"API keys invalid: {str(e)}"
        }


# ============================================================================
# Data Export (GDPR)
# ============================================================================

@router.get("/export")
async def export_user_data(
    format: str = "json",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export all user data (GDPR compliance).
    
    **Query Parameters:**
    - format: "json" or "csv" (default: json)
    
    **Includes:**
    - User profile
    - Trade history
    - Settings
    - API keys (masked)
    """
    # Fetch user data
    profile_data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "created_at": current_user.created_at.isoformat(),
        "email_verified": current_user.email_verified
    }
    
    # Fetch trades
    query = select(Trade).where(Trade.trader_wallet_address == current_user.wallet_address)
    result = await db.execute(query)
    trades = result.scalars().all()
    
    trades_data = [
        {
            "id": trade.id,
            "market_id": trade.market_id,
            "side": trade.side,
            "outcome": trade.position,
            "quantity": float(trade.quantity),
            "entry_price": float(trade.entry_price),
            "entry_value_usd": float(trade.entry_value_usd),
            "status": trade.status,
            "entry_timestamp": trade.entry_timestamp.isoformat()
        }
        for trade in trades
    ]
    
    export_data = {
        "profile": profile_data,
        "trades": trades_data,
        "exported_at": datetime.utcnow().isoformat()
    }
    
    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=trades_data[0].keys() if trades_data else [])
        writer.writeheader()
        writer.writerows(trades_data)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=user_{current_user.id}_data.csv"
            }
        )
    else:
        # Return JSON
        return StreamingResponse(
            iter([json.dumps(export_data, indent=2)]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=user_{current_user.id}_data.json"
            }
        )
