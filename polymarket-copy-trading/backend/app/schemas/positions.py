from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

# ========== POSITIONS SCHEMAS ==========

class PositionFilters(BaseModel):
    """Position filtering options"""
    trader_id: Optional[int] = None
    market_category: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    limit: int = 50

class OpenPositionResponse(BaseModel):
    """Open position response"""
    id: int
    market_id: str
    market_title: str
    side: str
    entry_price: float
    current_price: Optional[float]
    quantity: float
    amount_usd: float
    unrealized_pnl: float
    trader_wallet: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ClosedPositionResponse(BaseModel):
    """Closed position response"""
    id: int
    market_id: str
    market_title: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl: float
    duration_hours: float
    closed_at: datetime
    
    class Config:
        from_attributes = True

class ClosePositionRequest(BaseModel):
    """Manual position close request"""
    position_id: int

# ========== SETTINGS SCHEMAS ==========

class ProfileUpdateRequest(BaseModel):
    """Profile update"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = None
    full_name: Optional[str] = None
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

class ChangePasswordRequest(BaseModel):
    """Change password"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Must contain uppercase')
        if not any(c.islower() for c in v):
            raise ValueError('Must contain lowercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Must contain number')
        return v

class PolymarketKeysRequest(BaseModel):
    """Polymarket API keys"""
    api_key: str
    api_secret: str

class PolymarketKeysStatus(BaseModel):
    """Polymarket keys status"""
    is_configured: bool
    last_tested: Optional[datetime]
    is_valid: bool

class NotificationPreferencesRequest(BaseModel):
    """Update notification preferences"""
    email_trade_execution: Optional[bool] = None
    email_daily_summary: Optional[bool] = None
    email_security_alerts: Optional[bool] = None
    telegram_trade_execution: Optional[bool] = None
    telegram_daily_summary: Optional[bool] = None
    telegram_security_alerts: Optional[bool] = None
    notification_frequency: Optional[str] = Field(None, pattern="^(instant|hourly|daily)$")

class TradingPreferencesRequest(BaseModel):
    """Update trading preferences"""
    default_copy_percentage: Optional[float] = Field(None, ge=0.1, le=100)
    daily_spend_limit_usd: Optional[float] = Field(None, gt=0)
    weekly_spend_limit_usd: Optional[float] = Field(None, gt=0)
    slippage_tolerance: Optional[float] = Field(None, ge=0, le=10)
    auto_stop_loss_percentage: Optional[float] = Field(None, ge=0, le=100)
    auto_take_profit_percentage: Optional[float] = Field(None, ge=0, le=1000)

class UserPreferencesResponse(BaseModel):
    """User preferences response"""
    default_copy_percentage: float
    daily_spend_limit_usd: float
    weekly_spend_limit_usd: float
    slippage_tolerance: float
    auto_stop_loss_percentage: Optional[float]
    auto_take_profit_percentage: Optional[float]
    email_trade_execution: bool
    email_daily_summary: bool
    email_security_alerts: bool
    telegram_trade_execution: bool
    telegram_daily_summary: bool
    telegram_security_alerts: bool
    notification_frequency: str
    
    class Config:
        from_attributes = True

class SubscriptionUsage(BaseModel):
    """Subscription usage stats"""
    current_tier: str
    max_traders: int
    current_traders: int
    max_monthly_volume: Optional[float]
    current_monthly_volume: float

class BillingHistoryResponse(BaseModel):
    """Billing history item"""
    id: int
    amount: float
    currency: str
    description: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime]
    
    class Config:
        from_attributes = True
