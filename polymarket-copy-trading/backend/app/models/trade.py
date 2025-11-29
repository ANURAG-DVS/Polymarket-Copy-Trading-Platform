from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class TradeSide(str, enum.Enum):
    YES = "yes"
    NO = "no"

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relations
    trader_id = Column(Integer, ForeignKey("traders.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Null if it's the trader's own trade
    
    # Trade Details
    market_id = Column(String, nullable=False, index=True)
    market_title = Column(String, nullable=False)
    outcome = Column(String, nullable=False)
    side = Column(SQLEnum(TradeSide), nullable=False)
    
    # Pricing
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    
    # Quantities
    quantity = Column(Float, nullable=False)
    amount_usd = Column(Float, nullable=False)
    
    # P&L
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    
    # Status
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.OPEN, index=True)
    
    # External IDs
    polymarket_order_id = Column(String, nullable=True)
    blockchain_tx_hash = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Trade {self.id} - {self.market_title}>"
