"""
Polymarket API Client - Response Models

Pydantic models for type-safe API responses.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, validator


class Market(BaseModel):
    """Polymarket market data"""
    id: str = Field(..., description="Unique market identifier")
    question: str = Field(..., description="Market question")
    description: Optional[str] = Field(None, description="Market description")
    end_date: datetime = Field(..., description="Market close time")
    
    # Outcome tokens
    tokens: List[str] = Field(..., description="Token addresses for outcomes")
    outcome_prices: List[Decimal] = Field(..., description="Current outcome prices")
    
    # Market status
    active: bool = Field(..., description="Whether market is active")
    closed: bool = Field(..., description="Whether market is closed")
    resolved: bool = Field(False, description="Whether market is resolved")
    
    # Volume and liquidity
    volume: Decimal = Field(..., description="Total trading volume in USD")
    liquidity: Decimal = Field(..., description="Current liquidity in USD")
    
    # Metadata
    category: Optional[str] = Field(None, description="Market category")
    tags: List[str] = Field(default_factory=list, description="Market tags")
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class OrderBookLevel(BaseModel):
    """Single level in order book"""
    price: Decimal = Field(..., description="Price level")
    size: Decimal = Field(..., description="Total size at this price")
    
    class Config:
        json_encoders = {Decimal: str}


class OrderBook(BaseModel):
    """Order book for a market outcome"""
    market_id: str
    outcome: str  # "YES" or "NO"
    bids: List[OrderBookLevel] = Field(..., description="Buy orders (sorted by price desc)")
    asks: List[OrderBookLevel] = Field(..., description="Sell orders (sorted by price asc)")
    spread: Decimal = Field(..., description="Bid-ask spread")
    mid_price: Decimal = Field(..., description="Mid-market price")
    
    class Config:
        json_encoders = {Decimal: str}


class OrderStatus(BaseModel):
    """Status of a placed order"""
    order_id: str
    market_id: str
    side: str  # "BUY" or "SELL"
    outcome: str  # "YES" or "NO"
    price: Decimal
    size: Decimal
    filled_size: Decimal = Field(0, description="Amount filled")
    status: str  # "PENDING", "FILLED", "PARTIALLY_FILLED", "CANCELLED"
    created_at: datetime
    updated_at: datetime
    
    @property
    def is_active(self) -> bool:
        return self.status in ["PENDING", "PARTIALLY_FILLED"]
    
    @property
    def remaining_size(self) -> Decimal:
        return self.size - self.filled_size
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class Position(BaseModel):
    """User's position in a market"""
    market_id: str
    market_question: str
    outcome: str  # "YES" or "NO"
    quantity: Decimal = Field(..., description="Number of outcome tokens held")
    average_price: Decimal = Field(..., description="Average entry price")
    current_price: Decimal = Field(..., description="Current market price")
    
    # P&L
    cost_basis: Decimal = Field(..., description="Total cost in USD")
    current_value: Decimal = Field(..., description="Current value in USD")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")
    unrealized_pnl_percent: Decimal = Field(..., description="Unrealized P&L percentage")
    
    @validator('unrealized_pnl', always=True)
    def calculate_pnl(cls, v, values):
        if 'current_value' in values and 'cost_basis' in values:
            return values['current_value'] - values['cost_basis']
        return v
    
    @validator('unrealized_pnl_percent', always=True)
    def calculate_pnl_percent(cls, v, values):
        if 'unrealized_pnl' in values and 'cost_basis' in values:
            if values['cost_basis'] > 0:
                return (values['unrealized_pnl'] / values['cost_basis']) * 100
        return Decimal('0')
    
    class Config:
        json_encoders = {Decimal: str}


class TradeResult(BaseModel):
    """Result of a trade execution"""
    success: bool
    order_id: Optional[str] = None
    transaction_hash: Optional[str] = None
    
    # Trade details
    market_id: str
    side: str
    outcome: str
    size: Decimal
    price: Decimal
    
    # Execution info
    filled_size: Decimal = Field(0, description="Amount immediately filled")
    average_fill_price: Optional[Decimal] = None
    fees: Decimal = Field(0, description="Trading fees")
    
    # Status
    status: str = "PENDING"
    error: Optional[str] = None
    
    class Config:
        json_encoders = {Decimal: str}


class MarketPrices(BaseModel):
    """Current prices for a market"""
    market_id: str
    yes_price: Decimal = Field(..., description="YES outcome price (0-1)")
    no_price: Decimal = Field(..., description="NO outcome price (0-1)")
    last_updated: datetime
    
    @validator('no_price', always=True)
    def validate_prices_sum(cls, v, values):
        """Ensure YES and NO prices sum to ~1.0"""
        if 'yes_price' in values:
            total = values['yes_price'] + v
            # Allow small rounding errors
            if not (0.99 <= total <= 1.01):
                raise ValueError(f"YES ({values['yes_price']}) + NO ({v}) must sum to ~1.0")
        return v
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class Balance(BaseModel):
    """User's balance information"""
    usdc_balance: Decimal = Field(..., description="USDC balance")
    total_position_value: Decimal = Field(..., description="Total value of open positions")
    available_balance: Decimal = Field(..., description="Available for trading")
    
    class Config:
        json_encoders = {Decimal: str}
