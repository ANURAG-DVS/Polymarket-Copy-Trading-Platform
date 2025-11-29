from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from app.db.base_class import Base
import enum

class RelationshipStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"

class CopyRelationship(Base):
    __tablename__ = "copy_relationships"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relations
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trader_id = Column(Integer, ForeignKey("traders.id"), nullable=False, index=True)
    
    # Copy Settings
    copy_percentage = Column(Float, nullable=False)  # Percentage of trader's position size
    max_investment_usd = Column(Float, nullable=False)  # Maximum per trade
    
    # Performance from this trader
    total_pnl = Column(Float, default=0.0)
    total_trades_copied = Column(Integer, default=0)
    
    # Status
    status = Column(SQLEnum(RelationshipStatus), default=RelationshipStatus.ACTIVE, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    paused_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<CopyRelationship user:{self.user_id} -> trader:{self.trader_id}>"
