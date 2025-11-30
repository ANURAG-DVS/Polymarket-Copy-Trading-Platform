"""
Pydantic schemas for the enhanced trader data layer models.

These schemas handle validation and serialization for TraderV2, TraderStats,
and TraderMarket models from The Graph Protocol data.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class PositionSideEnum(str, Enum):
    """Position side enum"""
    YES = "YES"
    NO = "NO"


class PositionStatusEnum(str, Enum):
    """Position status enum"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


# ============================================================================
# Trader Schemas
# ============================================================================

class TraderV2Base(BaseModel):
    """
    Base schema for TraderV2 with common fields.
    
    This schema includes the core trader information that is shared
    across create, update, and response schemas.
    """
    wallet_address: str = Field(
        ...,
        min_length=42,
        max_length=42,
        description="Ethereum wallet address (42 characters including 0x)",
        examples=["0x1234567890123456789012345678901234567890"]
    )
    username: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional trader username or display name",
        examples=["TopTrader2024"]
    )


class TraderV2Create(TraderV2Base):
    """
    Schema for creating a new TraderV2 record.
    
    Includes initial performance metrics that can be set when creating
    a trader from The Graph Protocol data.
    """
    total_volume: Decimal = Field(
        default=Decimal("0.0"),
        ge=0,
        description="Total trading volume in USD",
        examples=[125000.50]
    )
    total_pnl: Decimal = Field(
        default=Decimal("0.0"),
        description="Total profit and loss in USD (can be negative)",
        examples=[12450.75]
    )
    win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Win rate percentage (0-100)",
        examples=[68.5]
    )
    total_trades: int = Field(
        default=0,
        ge=0,
        description="Total number of trades executed",
        examples=[145]
    )
    markets_traded: int = Field(
        default=0,
        ge=0,
        description="Number of unique markets traded",
        examples=[23]
    )
    last_trade_at: Optional[datetime] = Field(
        None,
        description="Timestamp of the last trade",
        examples=["2025-01-01T12:00:00Z"]
    )


class TraderV2Update(BaseModel):
    """
    Schema for updating an existing TraderV2 record.
    
    All fields are optional to allow partial updates.
    """
    username: Optional[str] = Field(None, max_length=100)
    total_volume: Optional[Decimal] = Field(None, ge=0)
    total_pnl: Optional[Decimal] = None
    win_rate: Optional[float] = Field(None, ge=0.0, le=100.0)
    total_trades: Optional[int] = Field(None, ge=0)
    markets_traded: Optional[int] = Field(None, ge=0)
    last_trade_at: Optional[datetime] = None


class TraderV2Response(TraderV2Base):
    """
    Schema for TraderV2 API responses.
    
    Includes all trader fields plus computed fields and timestamps.
    """
    total_volume: Decimal = Field(..., description="Total trading volume in USD")
    total_pnl: Decimal = Field(..., description="Total profit and loss in USD")
    win_rate: float = Field(..., description="Win rate percentage (0-100)")
    total_trades: int = Field(..., description="Total number of trades")
    markets_traded: int = Field(..., description="Number of unique markets")
    last_trade_at: Optional[datetime] = Field(None, description="Last trade timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    model_config = ConfigDict(from_attributes=True)


class TraderV2LeaderboardResponse(TraderV2Response):
    """
    Extended schema for leaderboard responses.
    
    Includes additional computed fields like rank that are calculated
    at query time.
    """
    rank: int = Field(
        ...,
        ge=1,
        description="Current rank position in leaderboard",
        examples=[1]
    )
    pnl_7d: Optional[Decimal] = Field(
        None,
        description="7-day profit and loss (computed from TraderStats)",
        examples=[2450.50]
    )
    pnl_30d: Optional[Decimal] = Field(
        None,
        description="30-day profit and loss (computed from TraderStats)",
        examples=[8920.75]
    )


# ============================================================================
# TraderStats Schemas
# ============================================================================

class TraderStatsBase(BaseModel):
    """
    Base schema for daily trader statistics.
    
    Contains the core time-series data for a trader's daily performance.
    """
    wallet_address: str = Field(
        ...,
        min_length=42,
        max_length=42,
        description="Trader's wallet address"
    )
    date: date = Field(
        ...,
        description="Date for this daily stat",
        examples=["2025-01-01"]
    )
    daily_pnl: Decimal = Field(
        default=Decimal("0.0"),
        description="Profit and loss for this day",
        examples=[450.25]
    )
    daily_volume: Decimal = Field(
        default=Decimal("0.0"),
        ge=0,
        description="Trading volume for this day",
        examples=[5000.00]
    )
    trades_count: int = Field(
        default=0,
        ge=0,
        description="Number of trades executed this day",
        examples=[12]
    )
    win_count: int = Field(
        default=0,
        ge=0,
        description="Number of winning trades",
        examples=[8]
    )
    loss_count: int = Field(
        default=0,
        ge=0,
        description="Number of losing trades",
        examples=[4]
    )
    
    @field_validator('win_count', 'loss_count')
    @classmethod
    def validate_win_loss(cls, v, info):
        """Ensure win + loss doesn't exceed total trades"""
        if info.data.get('trades_count') is not None:
            win = info.data.get('win_count', 0)
            loss = info.data.get('loss_count', 0)
            total = info.data.get('trades_count', 0)
            if win + loss > total:
                raise ValueError('Win count + Loss count cannot exceed total trades')
        return v


class TraderStatsCreate(TraderStatsBase):
    """Schema for creating a new TraderStats record."""
    pass


class TraderStatsResponse(TraderStatsBase):
    """
    Schema for TraderStats API responses.
    
    Includes the database ID and computed win rate.
    """
    id: int = Field(..., description="Database record ID")
    win_rate: float = Field(
        default=0.0,
        description="Daily win rate percentage (computed)",
        examples=[66.7]
    )
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# TraderMarket Schemas
# ============================================================================

class TraderMarketBase(BaseModel):
    """
    Base schema for trader market positions.
    
    Contains information about a specific position in a market.
    """
    wallet_address: str = Field(
        ...,
        min_length=42,
        max_length=42,
        description="Trader's wallet address"
    )
    market_id: str = Field(
        ...,
        max_length=100,
        description="Unique market identifier",
        examples=["0xmarket123"]
    )
    market_name: Optional[str] = Field(
        None,
        max_length=500,
        description="Human-readable market name",
        examples=["Will Bitcoin hit $100k by EOY 2025?"]
    )
    position_side: PositionSideEnum = Field(
        ...,
        description="Position side (YES or NO)",
        examples=["YES"]
    )
    entry_price: Decimal = Field(
        ...,
        gt=0,
        description="Entry price for the position (0-1)",
        examples=[0.72]
    )
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Quantity of shares/contracts",
        examples=[100.5]
    )
    status: PositionStatusEnum = Field(
        default=PositionStatusEnum.OPEN,
        description="Position status (OPEN or CLOSED)"
    )
    pnl: Decimal = Field(
        default=Decimal("0.0"),
        description="Current profit/loss for this position",
        examples=[125.50]
    )


class TraderMarketCreate(TraderMarketBase):
    """Schema for creating a new TraderMarket position."""
    pass


class TraderMarketUpdate(BaseModel):
    """
    Schema for updating a TraderMarket position.
    
    Typically used when a position is closed or P&L changes.
    """
    status: Optional[PositionStatusEnum] = None
    pnl: Optional[Decimal] = None
    closed_at: Optional[datetime] = None


class TraderMarketResponse(TraderMarketBase):
    """
    Schema for TraderMarket API responses.
    
    Includes all position fields plus timestamps.
    """
    id: int = Field(..., description="Database record ID")
    created_at: datetime = Field(..., description="Position creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    closed_at: Optional[datetime] = Field(None, description="Position close timestamp")
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# List/Paginated Responses
# ============================================================================

class TraderV2ListResponse(BaseModel):
    """Paginated list of traders"""
    traders: List[TraderV2Response]
    total: int = Field(..., description="Total number of traders")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class TraderStatsListResponse(BaseModel):
    """List of trader stats (time-series data)"""
    stats: List[TraderStatsResponse]
    total: int
    wallet_address: str


class TraderMarketListResponse(BaseModel):
    """List of trader positions"""
    positions: List[TraderMarketResponse]
    total: int
    open_count: int = Field(..., description="Number of open positions")
    closed_count: int = Field(..., description="Number of closed positions")
    total_pnl: Decimal = Field(..., description="Total P&L across all positions")
