from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.base_class import Base

class Trader(Base):
    __tablename__ = "traders"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    
    # Performance Metrics
    total_pnl = Column(Float, default=0.0)
    pnl_7d = Column(Float, default=0.0)
    pnl_30d = Column(Float, default=0.0)
    pnl_all_time = Column(Float, default=0.0)
    
    # Trading Stats
    win_rate = Column(Float, default=0.0)  # Percentage
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    # Trade Sizes
    avg_trade_size = Column(Float, default=0.0)
    max_trade_size = Column(Float, default=0.0)
    total_volume = Column(Float, default=0.0)
    
    # Risk Metrics
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    
    # Ranking
    rank = Column(Integer, nullable=True, index=True)
    rank_7d = Column(Integer, nullable=True)
    rank_30d = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_trade_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Trader {self.wallet_address}>"
