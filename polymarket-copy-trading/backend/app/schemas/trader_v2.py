"""
Pydantic schemas for the enhanced trader data layer models.

These schemas handle validation and serialization for TraderV2, TraderStats,
and TraderMarket models from The Graph Protocol data.

CRITICAL: Schemas do NOT include relationship fields to prevent RecursionError.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime, date as date_type
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
# BASE SCHEMAS (No relationships)
# ============================================================================

class TraderV2Base(BaseModel):
    """
    Base schema for TraderV2 with common fields.
    NO RELATIONSHIPS - only scalar fields.
    """
    wallet_address: str = Field(
        ...,
        min_length=42,
        max_length=42,
        description="Ethereum wallet address (42 characters including 0x)"
    )
    username: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional trader username"
    )
    
    @field_validator('wallet_address')
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        """Ensure wallet address is valid Ethereum format"""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum wallet address')
        return v.lower()  # Normalize to lowercase


class TraderStatsBase(BaseModel):
    """
    Base schema for daily trader statistics.
    NO RELATIONSHIPS - only scalar fields.
    """
    wallet_address: str = Field(..., min_length=42, max_length=42)
    date: date_type = Field(..., description="Date for this daily stat")
    daily_pnl: Decimal = Field(default=Decimal("0.0"))
    daily_volume: Decimal = Field(default=Decimal("0.0"), ge=0)
    trades_count: int = Field(default=0, ge=0)
    win_count: int = Field(default=0, ge=0)
    loss_count: int = Field(default=0, ge=0)
    
    @field_validator('wallet_address')
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        """Ensure wallet address is valid"""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum wallet address')
        return v.lower()


class TraderMarketBase(BaseModel):
    """
    Base schema for trader market positions.
    NO RELATIONSHIPS - only scalar fields.
    """
    wallet_address: str = Field(..., min_length=42, max_length=42)
    market_id: str = Field(..., max_length=100)
    market_name: Optional[str] = Field(None, max_length=500)
    position_side: PositionSideEnum
    entry_price: Optional[Decimal] = Field(None, gt=0)
    quantity: Optional[Decimal] = Field(None, gt=0)
    status: PositionStatusEnum = PositionStatusEnum.OPEN
    pnl: Decimal = Field(default=Decimal("0.0"))
    
    @field_validator('wallet_address')
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        """Ensure wallet address is valid"""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum wallet address')
        return v.lower()


# ============================================================================
# RESPONSE SCHEMAS (Safe for API - NO relationships)
# ============================================================================

class TraderV2Response(TraderV2Base):
    """
    Response schema for single trader - NO relationships.
    Safe to serialize without recursion.
    """
    total_volume: Decimal = Field(..., description="Total trading volume")
    total_pnl: Decimal = Field(..., description="Total P&L")
    win_rate: float = Field(..., ge=0.0, le=100.0)
    total_trades: int = Field(..., ge=0)
    markets_traded: int = Field(..., ge=0)
    last_trade_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class TraderV2LeaderboardResponse(TraderV2Response):
    """
    Extended schema for leaderboard responses.
    Includes rank but still NO relationships.
    """
    rank: int = Field(..., ge=1, description="Leaderboard rank")
    pnl_7d: Optional[Decimal] = Field(None, description="7-day P&L")
    pnl_30d: Optional[Decimal] = Field(None, description="30-day P&L")
    win_rate_7d: Optional[float] = Field(None, ge=0.0, le=100.0)
    
    model_config = ConfigDict(from_attributes=True)


class TraderStatsResponse(TraderStatsBase):
    """
    Response for trader statistics - NO relationship to parent.
    """
    id: int
    win_rate: float = Field(default=0.0, description="Daily win rate")
    
    model_config = ConfigDict(from_attributes=True)


class TraderMarketResponse(TraderMarketBase):
    """
    Response for trader markets - NO relationship to parent.
    """
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# DETAILED RESPONSES (Controlled - uses counts, not nested objects)
# ============================================================================

class TraderV2DetailResponse(TraderV2Response):
    """
    Detailed trader info with stats summary (NOT full nested objects).
    Use this for GET /traders/{address} endpoint.
    """
    # Use counts instead of including relationship lists
    stats_count: int = Field(default=0, description="Number of stat records")
    markets_count: int = Field(default=0, description="Number of market positions")
    
    # Optionally include recent data as separate explicit fields
    recent_stats: Optional[List[TraderStatsResponse]] = None
    recent_markets: Optional[List[TraderMarketResponse]] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# CREATE/UPDATE SCHEMAS
# ============================================================================

class TraderV2Create(TraderV2Base):
    """Schema for creating new trader"""
    total_volume: Decimal = Field(default=Decimal("0.0"), ge=0)
    total_pnl: Decimal = Field(default=Decimal("0.0"))
    win_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    total_trades: int = Field(default=0, ge=0)
    markets_traded: int = Field(default=0, ge=0)
    last_trade_at: Optional[datetime] = None


class TraderV2Update(BaseModel):
    """Schema for updating trader (all fields optional)"""
    username: Optional[str] = Field(None, max_length=100)
    total_volume: Optional[Decimal] = Field(None, ge=0)
    total_pnl: Optional[Decimal] = None
    win_rate: Optional[float] = Field(None, ge=0.0, le=100.0)
    total_trades: Optional[int] = Field(None, ge=0)
    markets_traded: Optional[int] = Field(None, ge=0)
    last_trade_at: Optional[datetime] = None


class TraderStatsCreate(TraderStatsBase):
    """Schema for creating new TraderStats record"""
    pass


class TraderMarketCreate(TraderMarketBase):
    """Schema for creating new TraderMarket position"""
    pass


class TraderMarketUpdate(BaseModel):
    """Schema for updating a TraderMarket position"""
    status: Optional[PositionStatusEnum] = None
    pnl: Optional[Decimal] = None
    closed_at: Optional[datetime] = None


# ============================================================================
# SEARCH/FILTER SCHEMAS
# ============================================================================

class TraderSearchResult(BaseModel):
    """Minimal trader info for search results - NO relationships"""
    wallet_address: str
    username: Optional[str] = None
    total_pnl: Decimal
    win_rate: float
    total_trades: int
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# LIST/PAGINATED RESPONSES
# ============================================================================

class TraderV2ListResponse(BaseModel):
    """Paginated list of traders - NO nested relationships"""
    traders: List[TraderV2Response]
    total: int = Field(..., description="Total number of traders")
    page: int = Field(..., ge=1)
    limit: int = Field(..., ge=1, le=100)
    total_pages: int


class TraderStatsListResponse(BaseModel):
    """List of trader stats - NO parent relationship"""
    stats: List[TraderStatsResponse]
    total: int
    wallet_address: str


class TraderMarketListResponse(BaseModel):
    """List of trader positions - NO parent relationship"""
    positions: List[TraderMarketResponse]
    total: int
    open_count: int = Field(..., description="Number of open positions")
    closed_count: int = Field(..., description="Number of closed positions")
    total_pnl: Decimal
