from fastapi import APIRouter, Query
from typing import List, Dict
from app.services.polymarket_service import polymarket_service
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class TopTradeResponse(BaseModel):
    """Response schema for top trades"""
    market_id: str
    market_title: str
    outcome: str
    volume_24h: float
    current_price: float
    liquidity: float
    end_date: str
    created_at: str
    image_url: str
    category: str

@router.get("/top", response_model=List[TopTradeResponse])
async def get_top_trades(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    limit: int = Query(10, ge=1, le=50, description="Number of top trades")
):
    """
    Get top trades from Polymarket by volume in the last N hours
    
    Returns the highest volume markets/trades sorted by 24h volume
    """
    trades = await polymarket_service.get_top_trades(hours=hours, limit=limit)
    return trades
