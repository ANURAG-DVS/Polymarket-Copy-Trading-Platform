"""
Enhanced SQLAlchemy models for trader performance data from The Graph Protocol.
This file contains the new data layer models separate from the existing trader models.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Numeric, ForeignKey, Index, CheckConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum
from app.db.base_class import Base


class PositionSide(str, enum.Enum):
    """Position side enum for trader markets"""
    YES = "YES"
    NO = "NO"


class PositionStatus(str, enum.Enum):
    """Position status enum for trader markets"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TraderV2(Base):
    """
    Enhanced Trader model for storing trader performance data from The Graph Protocol.
    
    This model represents top traders on Polymarket with their overall
    performance metrics and statistics. Uses wallet_address as primary key
    for better integration with blockchain data.
    """
    __tablename__ = "traders_v2"
    
    # Primary Key
    wallet_address = Column(String(42), primary_key=True, index=True, nullable=False)
    
    # Profile Information
    username = Column(String(100), nullable=True)
    
    # Performance Metrics
    total_volume = Column(Numeric(20, 2), default=0.0, nullable=False)
    total_pnl = Column(Numeric(20, 2), default=0.0, nullable=False)
    win_rate = Column(Float, default=0.0, nullable=False)
    
    # Trading Activity
    total_trades = Column(Integer, default=0, nullable=False)
    markets_traded = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    last_trade_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    stats = relationship(
        "TraderStats",
        back_populates="trader",
        cascade="all, delete-orphan",
        lazy="dynamic",
        repr=False  # Prevent circular reference in repr
    )
    
    markets = relationship(
        "TraderMarket",
        back_populates="trader",
        cascade="all, delete-orphan",
        lazy="dynamic",
        repr=False  # Prevent circular reference in repr
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint('win_rate >= 0 AND win_rate <= 100', name='check_win_rate_range'),
        CheckConstraint('total_trades >= 0', name='check_total_trades_positive'),
        CheckConstraint('markets_traded >= 0', name='check_markets_traded_positive'),
        Index('idx_trader_total_pnl', 'total_pnl'),
        Index('idx_trader_win_rate', 'win_rate'),
        Index('idx_trader_total_volume', 'total_volume'),
        Index('idx_trader_performance', 'total_pnl', 'win_rate', 'total_volume'),  # Composite index for leaderboard
    )
    
    def __repr__(self):
        """String representation for debugging"""
        return (
            f"<TraderV2(wallet={self.wallet_address[:10]}..., "
            f"username={self.username}, "
            f"pnl={self.total_pnl}, "
            f"win_rate={self.win_rate}%)>"
        )
    
    def to_dict(self):
        """Convert model to dictionary for serialization"""
        return {
            'wallet_address': self.wallet_address,
            'username': self.username,
            'total_volume': float(self.total_volume) if self.total_volume else 0.0,
            'total_pnl': float(self.total_pnl) if self.total_pnl else 0.0,
            'win_rate': float(self.win_rate) if self.win_rate else 0.0,
            'total_trades': self.total_trades,
            'markets_traded': self.markets_traded,
            'last_trade_at': self.last_trade_at.isoformat() if self.last_trade_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def calculate_7d_rank(self, db_session):
        """
        Calculate trader's rank based on 7-day P&L.
        
        Args:
            db_session: SQLAlchemy database session
            
        Returns:
            int: Rank position (1-indexed)
        """
        from sqlalchemy import func as sql_func
        
        # Calculate 7-day P&L from TraderStats
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Subquery to get 7-day P&L for this trader
        pnl_7d = db_session.query(
            sql_func.sum(TraderStats.daily_pnl)
        ).filter(
            TraderStats.wallet_address == self.wallet_address,
            TraderStats.date >= seven_days_ago
        ).scalar() or 0
        
        # Count how many traders have higher 7-day P&L
        rank = db_session.query(
            sql_func.count(sql_func.distinct(TraderV2.wallet_address))
        ).join(
            TraderStats,
            TraderStats.wallet_address == TraderV2.wallet_address
        ).filter(
            TraderStats.date >= seven_days_ago
        ).group_by(
            TraderV2.wallet_address
        ).having(
            sql_func.sum(TraderStats.daily_pnl) > pnl_7d
        ).count()
        
        return rank + 1


class TraderStats(Base):
    """
    Time-series model for trader daily statistics.
    
    This model is designed to be a TimescaleDB hypertable for efficient
    time-series queries and analytics.
    """
    __tablename__ = "trader_stats"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    wallet_address = Column(
        String(42),
        ForeignKey('traders_v2.wallet_address', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Date for time-series
    date = Column(Date, nullable=False, index=True)
    
    # Daily Performance Metrics
    daily_pnl = Column(Numeric(20, 2), default=0.0, nullable=False)
    daily_volume = Column(Numeric(20, 2), default=0.0, nullable=False)
    
    # Daily Trading Activity
    trades_count = Column(Integer, default=0, nullable=False)
    win_count = Column(Integer, default=0, nullable=False)
    loss_count = Column(Integer, default=0, nullable=False)
    
    # Relationship
    trader = relationship("TraderV2", back_populates="stats", repr=False)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_trader_stats_wallet_date', 'wallet_address', 'date', unique=True),
        Index('idx_trader_stats_date', 'date'),
        Index('idx_trader_stats_pnl', 'daily_pnl'),
        CheckConstraint('trades_count >= 0', name='check_trades_count_positive'),
        CheckConstraint('win_count >= 0', name='check_win_count_positive'),
        CheckConstraint('loss_count >= 0', name='check_loss_count_positive'),
        CheckConstraint('win_count + loss_count <= trades_count', name='check_win_loss_sum'),
    )
    
    def __repr__(self):
        """String representation for debugging"""
        return (
            f"<TraderStats(wallet={self.wallet_address[:10]}..., "
            f"date={self.date}, "
            f"pnl={self.daily_pnl}, "
            f"trades={self.trades_count})>"
        )
    
    def to_dict(self):
        """Convert model to dictionary for serialization"""
        return {
            'id': self.id,
            'wallet_address': self.wallet_address,
            'date': self.date.isoformat() if self.date else None,
            'daily_pnl': float(self.daily_pnl) if self.daily_pnl else 0.0,
            'daily_volume': float(self.daily_volume) if self.daily_volume else 0.0,
            'trades_count': self.trades_count,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate': (self.win_count / self.trades_count * 100) if self.trades_count > 0 else 0.0,
        }


class TraderMarket(Base):
    """
    Model for tracking individual market positions held by traders.
    
    This model stores each position a trader takes in a specific market,
    allowing for detailed tracking of trading activity.
    """
    __tablename__ = "trader_markets"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    wallet_address = Column(
        String(42),
        ForeignKey('traders_v2.wallet_address', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Market Information
    market_id = Column(String(100), nullable=False, index=True)
    market_name = Column(String(500), nullable=True)
    
    # Position Details
    position_side = Column(SQLEnum(PositionSide), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    
    # Position Status
    status = Column(SQLEnum(PositionStatus), default=PositionStatus.OPEN, nullable=False, index=True)
    pnl = Column(Numeric(20, 2), default=0.0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    trader = relationship("TraderV2", back_populates="markets", repr=False)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_trader_market_wallet', 'wallet_address', 'market_id'),
        Index('idx_trader_market_status', 'status'),
        Index('idx_trader_market_pnl', 'pnl'),
        CheckConstraint('entry_price > 0', name='check_entry_price_positive'),
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )
    
    def __repr__(self):
        """String representation for debugging"""
        return (
            f"<TraderMarket(wallet={self.wallet_address[:10]}..., "
            f"market={self.market_id[:10]}..., "
            f"side={self.position_side.value}, "
            f"status={self.status.value}, "
            f"pnl={self.pnl})>"
        )
    
    def to_dict(self):
        """Convert model to dictionary for serialization"""
        return {
            'id': self.id,
            'wallet_address': self.wallet_address,
            'market_id': self.market_id,
            'market_name': self.market_name,
            'position_side': self.position_side.value if self.position_side else None,
            'entry_price': float(self.entry_price) if self.entry_price else 0.0,
            'quantity': float(self.quantity) if self.quantity else 0.0,
            'status': self.status.value if self.status else None,
            'pnl': float(self.pnl) if self.pnl else 0.0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
        }
