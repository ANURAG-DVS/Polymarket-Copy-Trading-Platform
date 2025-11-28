"""
SQLAlchemy Models for API Key Management

Supporting models for the API key management system.
"""

from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP, Integer, ForeignKey, Boolean, Numeric, JSON
from sqlalchemy.dialects.postgresql import INET
from datetime import datetime

from app.db.session import Base


class APIKey(Base):
    """Model for polymarket_api_keys table"""
    __tablename__ = 'polymarket_api_keys'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    encrypted_api_key = Column('encrypted_api_key', type_=bytes, nullable=False)
    encrypted_api_secret = Column('encrypted_api_secret', type_=bytes, nullable=False)
    encrypted_private_key = Column('encrypted_private_key', type_=bytes, nullable=True)
    
    key_name = Column(String(100), nullable=True)
    key_hash = Column(String(64), unique=True, nullable=False)
    
    daily_spend_limit_usd = Column(Numeric(12, 2), nullable=False, default=1000.00)
    daily_spent_usd = Column(Numeric(12, 2), nullable=False, default=0)
    last_reset_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    total_trades_executed = Column(Integer, nullable=False, default=0)
    total_volume_usd = Column(Numeric(20, 6), nullable=False, default=0)
    
    status = Column(String(20), nullable=False, default='active')
    is_primary = Column(Boolean, nullable=False, default=False)
    
    last_used_at = Column(TIMESTAMP, nullable=True)
    revoked_at = Column(TIMESTAMP, nullable=True)
    revoked_reason = Column(Text, nullable=True)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(TIMESTAMP, nullable=True)


class User(Base):
    """Model for users table"""
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=True)
    wallet_address = Column(String(42), unique=True, nullable=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)
    username = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)
    
    subscription_tier = Column(String(20), nullable=False, default='free')
    max_followed_traders = Column(Integer, nullable=False, default=3)
    max_daily_trades = Column(Integer, nullable=False, default=10)
    max_trade_size_usd = Column(Numeric(12, 2), nullable=False, default=100.00)
    max_total_exposure_usd = Column(Numeric(12, 2), nullable=False, default=500.00)
    
    balance_usd = Column(Numeric(20, 6), nullable=False, default=0)
    total_spent_usd = Column(Numeric(20, 6), nullable=False, default=0)
    total_earned_usd = Column(Numeric(20, 6), nullable=False, default=0)
    
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    two_factor_enabled = Column(Boolean, nullable=False, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    
    email_notifications = Column(Boolean, nullable=False, default=True)
    telegram_notifications = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(TIMESTAMP, nullable=True)


class Trade(Base):
    """Model for trades table"""
    __tablename__ = 'trades'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    original_tx_hash = Column(String(66), nullable=True)
    copy_tx_hash = Column(String(66), unique=True, nullable=True)
    
    trader_wallet_address = Column(String(42), nullable=False)
    copying_user_id = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    copy_relationship_id = Column(BigInteger, nullable=True)
    
    is_copy_trade = Column(Boolean, nullable=False, default=False)
    trade_type = Column(String(20), nullable=False, default='market')
    
    market_id = Column(String(100), nullable=False)
    market_name = Column(String(500), nullable=True)
    market_question = Column(Text, nullable=True)
    position = Column(String(10), nullable=False)
    
    entry_price = Column(Numeric(20, 10), nullable=False)
    exit_price = Column(Numeric(20, 10), nullable=True)
    quantity = Column(Numeric(20, 6), nullable=False)
    
    entry_value_usd = Column(Numeric(20, 6), nullable=False)
    exit_value_usd = Column(Numeric(20, 6), nullable=True)
    fees_usd = Column(Numeric(20, 6), nullable=False, default=0)
    gas_fee_usd = Column(Numeric(12, 6), nullable=False, default=0)
    
    realized_pnl_usd = Column(Numeric(20, 6), nullable=True)
    realized_pnl_percent = Column(Numeric(10, 4), nullable=True)
    unrealized_pnl_usd = Column(Numeric(20, 6), nullable=True)
    current_value_usd = Column(Numeric(20, 6), nullable=True)
    
    status = Column(String(20), nullable=False, default='pending')
    failure_reason = Column(Text, nullable=True)
    
    slippage_percent = Column(Numeric(5, 2), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    entry_timestamp = Column(TIMESTAMP, nullable=False)
    exit_timestamp = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Model for audit_logs table"""
    __tablename__ = 'audit_logs'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
