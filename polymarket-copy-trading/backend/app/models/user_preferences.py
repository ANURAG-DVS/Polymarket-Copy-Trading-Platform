from sqlalchemy import Column, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    
    # User relation
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Trading Preferences
    default_copy_percentage = Column(Float, default=5.0)
    daily_spend_limit_usd = Column(Float, default=100.0)
    weekly_spend_limit_usd = Column(Float, default=500.0)
    slippage_tolerance = Column(Float, default=1.0)  # Percentage
    
    # Auto-close Rules
    auto_stop_loss_percentage = Column(Float, nullable=True)  # If set, auto-close on loss
    auto_take_profit_percentage = Column(Float, nullable=True)  # If set, auto-close on profit
    
    # Notification Preferences
    email_trade_execution = Column(Boolean, default=True)
    email_daily_summary = Column(Boolean, default=False)
    email_security_alerts = Column(Boolean, default=True)
    
    telegram_trade_execution = Column(Boolean, default=False)
    telegram_daily_summary = Column(Boolean, default=False)
    telegram_security_alerts = Column(Boolean, default=True)
    
    notification_frequency = Column(String, default="instant")  # instant, hourly, daily
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<UserPreferences user:{self.user_id}>"

class BillingHistory(Base):
    __tablename__ = "billing_history"

    id = Column(Integer, primary_key=True, index=True)
    
    # User relation
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Billing details
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    description = Column(String, nullable=False)
    status = Column(String, nullable=False)  # succeeded, failed, pending
    
    # Stripe IDs
    stripe_invoice_id = Column(String, nullable=True)
    stripe_payment_intent_id = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<BillingHistory {self.id} - ${self.amount}>"
