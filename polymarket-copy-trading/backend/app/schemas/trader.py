from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class TraderBase(BaseModel):
    """Base trader schema"""
    wallet_address: str

class TraderResponse(BaseModel):
    """Trader response schema"""
    id: int
    wallet_address: str
    total_pnl: float
    pnl_7d: float
    pnl_30d: float
    pnl_all_time: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_size: float
    max_trade_size: float
    total_volume: float
    sharpe_ratio: float
    max_drawdown: float
    rank: Optional[int]
    rank_7d: Optional[int]
    rank_30d: Optional[int]
    is_active: bool
    last_trade_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TraderListResponse(BaseModel):
    """Paginated trader list response"""
    traders: List[TraderResponse]
    total: int
    page: int
    limit: int
    total_pages: int

class TradeResponse(BaseModel):
    """Trade response schema"""
    id: int
    market_id: str
    market_title: str
    outcome: str
    side: str
    entry_price: float
    exit_price: Optional[float]
    current_price: Optional[float]
    quantity: float
    amount_usd: float
    realized_pnl: float
    unrealized_pnl: float
    status: str
    created_at: datetime
    closed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class CopyRelationshipCreate(BaseModel):
    """Create copy relationship schema"""
    trader_id: int
    copy_percentage: float = Field(..., ge=0.1, le=100)
    max_investment_usd: float = Field(..., gt=0)
    
    @validator('copy_percentage')
    def validate_percentage(cls, v):
        if v < 0.1 or v > 100:
            raise ValueError('Copy percentage must be between 0.1 and 100')
        return v

class CopyRelationshipResponse(BaseModel):
    """Copy relationship response schema"""
    id: int
    user_id: int
    trader_id: int
    trader: Optional[TraderResponse]
    copy_percentage: float
    max_investment_usd: float
    total_pnl: float
    total_trades_copied: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TraderFilters(BaseModel):
    """Trader filtering options"""
    timeframe: str = "7d"  # 7d, 30d, all
    min_pnl: Optional[float] = None
    min_win_rate: Optional[float] = None
    min_trades: Optional[int] = None
    search: Optional[str] = None
    page: int = 1
    limit: int = 50
    sort_by: str = "rank"  # rank, pnl_7d, win_rate, total_trades
    sort_order: str = "asc"  # asc, desc
