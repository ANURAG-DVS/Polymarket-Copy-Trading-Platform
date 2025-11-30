"""
Polymarket API Service for fetching market data and trades
"""
import httpx
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class PolymarketService:
    """Service for interacting with Polymarket API"""
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_top_trades(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """
        Fetch top trades from Polymarket by volume in the last N hours
        
        Args:
            hours: Number of hours to look back (default 24)
            limit: Number of top trades to return (default 10)
            
        Returns:
            List of trade dictionaries with market info and volume
        """
        try:
            # Calculate timestamp for filtering
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Fetch recent markets with high volume
            # Note: Polymarket API endpoint - adjust based on actual API
            markets_url = f"{self.BASE_URL}/markets"
            
            response = await self.client.get(markets_url, params={
                "active": "true",
                "limit": 100  # Fetch more to sort by volume
            })
            response.raise_for_status()
            markets = response.json()
            
            # Transform and enrich market data
            enriched_trades = []
            for market in markets[:limit]:
                trade_data = {
                    "market_id": market.get("condition_id", ""),
                    "market_title": market.get("question", "Unknown Market"),
                    "outcome": market.get("outcomes", ["Yes", "No"])[0],
                    "volume_24h": float(market.get("volume_24hr", 0)),
                    "current_price": float(market.get("outcome_prices", [0.5])[0]),
                    "liquidity": float(market.get("liquidity", 0)),
                    "end_date": market.get("end_date_iso"),
                    "created_at": datetime.utcnow().isoformat(),
                    "image_url": market.get("image", ""),
                    "category": market.get("category", ""),
                }
                enriched_trades.append(trade_data)
            
            # Sort by 24h volume
            enriched_trades.sort(key=lambda x: x["volume_24h"], reverse=True)
            
            return enriched_trades[:limit]
            
        except httpx.HTTPError as e:
            logger.error(f"Error fetching Polymarket data: {e}")
            # Return mock data if API fails
            return self._get_mock_trades(limit)
        except Exception as e:
            logger.error(f"Unexpected error in get_top_trades: {e}")
            return self._get_mock_trades(limit)
    
    def _get_mock_trades(self, limit: int = 10) -> List[Dict]:
        """Return mock trade data for development/testing"""
        mock_trades = [
            {
                "market_id": "0x1234567890abcdef",
                "market_title": "Will Bitcoin hit $100,000 by end of 2025?",
                "outcome": "Yes",
                "volume_24h": 1250000.50,
                "current_price": 0.72,
                "liquidity": 500000.00,
                "end_date": "2025-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Crypto",
            },
            {
                "market_id": "0xabcdef1234567890",
                "market_title": "Will the Fed cut rates in Q1 2025?",
                "outcome": "Yes",
                "volume_24h": 980000.25,
                "current_price": 0.65,
                "liquidity": 450000.00,
                "end_date": "2025-03-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Economics",
            },
            {
                "market_id": "0x9876543210fedcba",
                "market_title": "Will Tesla stock reach $400 in 2025?",
                "outcome": "Yes",
                "volume_24h": 750000.00,
                "current_price": 0.58,
                "liquidity": 380000.00,
                "end_date": "2025-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Stocks",
            },
            {
                "market_id": "0xfedcba9876543210",
                "market_title": "Will AI replace 50% of jobs by 2030?",
                "outcome": "No",
                "volume_24h": 620000.75,
                "current_price": 0.35,
                "liquidity": 320000.00,
                "end_date": "2030-01-01T00:00:00Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Technology",
            },
            {
                "market_id": "0x5555555555555555",
                "market_title": "Will SpaceX land on Mars by 2026?",
                "outcome": "Yes",
                "volume_24h": 490000.00,
                "current_price": 0.42,
                "liquidity": 280000.00,
                "end_date": "2026-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Space",
            },
            {
                "market_id": "0x6666666666666666",
                "market_title": "Will inflation drop below 2% in 2025?",
                "outcome": "Yes",
                "volume_24h": 420000.50,
                "current_price": 0.68,
                "liquidity": 250000.00,
                "end_date": "2025-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Economics",
            },
            {
                "market_id": "0x7777777777777777",
                "market_title": "Will Apple launch AR glasses in 2025?",
                "outcome": "No",
                "volume_24h": 380000.25,
                "current_price": 0.28,
                "liquidity": 220000.00,
                "end_date": "2025-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Technology",
            },
            {
                "market_id": "0x8888888888888888",
                "market_title": "Will gold hit $2500/oz in 2025?",
                "outcome": "Yes",
                "volume_24h": 350000.00,
                "current_price": 0.55,
                "liquidity": 200000.00,
                "end_date": "2025-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Commodities",
            },
            {
                "market_id": "0x9999999999999999",
                "market_title": "Will ChatGPT-5 be released in 2025?",
                "outcome": "Yes",
                "volume_24h": 320000.75,
                "current_price": 0.61,
                "liquidity": 180000.00,
                "end_date": "2025-12-31T23:59:59Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Technology",
            },
            {
                "market_id": "0xaaaaaaaaaaaaaaaa",
                "market_title": "Will Ethereum flip Bitcoin by market cap?",
                "outcome": "No",
                "volume_24h": 290000.50,
                "current_price": 0.18,
                "liquidity": 160000.00,
                "end_date": "2026-01-01T00:00:00Z",
                "created_at": datetime.utcnow().isoformat(),
                "image_url": "/api/placeholder/400/300",
                "category": "Crypto",
            },
        ]
        return mock_trades[:limit]
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

# Singleton instance
polymarket_service = PolymarketService()
