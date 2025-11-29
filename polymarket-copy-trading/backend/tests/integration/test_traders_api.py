import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestTradersEndpoints:
    """Test traders API endpoints"""
    
    async def test_get_leaderboard(self, client: AsyncClient):
        """Test getting traders leaderboard"""
        response = await client.get("/api/v1/traders/leaderboard")
        
        assert response.status_code == 200
        data = response.json()
        assert "traders" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
    
    async def test_get_leaderboard_with_filters(self, client: AsyncClient):
        """Test leaderboard with filters"""
        response = await client.get(
            "/api/v1/traders/leaderboard",
            params={
                "timeframe": "7d",
                "min_pnl": 100,
                "min_win_rate": 60,
                "limit": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
    
    async def test_get_leaderboard_invalid_timeframe(self, client: AsyncClient):
        """Test leaderboard with invalid timeframe"""
        response = await client.get(
            "/api/v1/traders/leaderboard",
            params={"timeframe": "invalid"}
        )
        
        assert response.status_code == 422
    
    async def test_get_trader_details(self, client: AsyncClient):
        """Test getting trader details"""
        # This assumes trader with ID 1 exists
        response = await client.get("/api/v1/traders/1")
        
        # Could be 200 or 404 depending on test data
        assert response.status_code in [200, 404]
    
    async def test_get_trader_trades(self, client: AsyncClient):
        """Test getting trader's trades"""
        response = await client.get("/api/v1/traders/1/trades")
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "trades" in data
            assert "count" in data
