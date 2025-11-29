from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.base_class import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    # User relation
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Notification details
    type = Column(String, nullable=False, index=True)  # trade_executed, position_closed, low_balance, warning, info
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    # Related entities (optional)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=True)
    trader_id = Column(Integer, ForeignKey("traders.id"), nullable=True)
    
    # Status
    is_read = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Notification {self.id} - {self.type}>"

class UserBalance(Base):
    __tablename = "user_balances"

    id = Column(Integer, primary_key=True, index=True)
    
    # User relation
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Balance
    available_balance = Column(Float, default=0.0, nullable=False)
    locked_balance = Column(Float, default=0.0, nullable=False)  # In open positions
    
    # Timestamps
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<UserBalance user:{self.user_id} - ${self.available_balance}>"
