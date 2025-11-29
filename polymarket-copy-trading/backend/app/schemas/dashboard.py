from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DashboardOverview(BaseModel):
    """Dashboard overview data"""
    total_pnl: float
    pnl_7d_change: float  # Percentage change
    pnl_sparkline: List[float]  # Last 7 days
    
    active_copies: int
    active_traders: List[dict]  # List of trader info [{id, wallet_address, avatar}]
    
    open_positions: int
    open_positions_value: float
    
    available_balance: float
    locked_balance: float

class PLChartData(BaseModel):
    """P&L chart data point"""
    date: str
    pnl: float
    label: Optional[str] = None  # For grouping by market or trader

class PLChartResponse(BaseModel):
    """P&L chart response"""
    data: List[PLChartData]
    total_pnl: float
    period: str

class RecentTrade(BaseModel):
    """Recent trade summary"""
    id: int
    market_title: str
    side: str
    entry_price: float
    current_price: Optional[float]
    unrealized_pnl: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    """Notification response"""
    id: int
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class DashboardResponse(BaseModel):
    """Complete dashboard response"""
    overview: DashboardOverview
    recent_trades: List[RecentTrade]
    notifications: List[NotificationResponse]
