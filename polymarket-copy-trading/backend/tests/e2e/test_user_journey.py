import pytest
import asyncio
from httpx import AsyncClient
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteUserJourney:
    """End-to-end test of complete user journey"""
    
    async def test_complete_user_flow(self, client: AsyncClient, db_session: AsyncSession):
        """Test complete user journey from signup to trade execution"""
        
        logger.info("="*60)
        logger.info("STARTING COMPLETE USER JOURNEY TEST")
        logger.info("="*60)
        
        # Step 1: User Registration
        logger.info("\n1️⃣  Testing user registration...")
        register_response = await client.post("/api/v1/auth/register", json={
            "email": "testuser@example.com",
            "username": "testuser",
            "password": "SecurePassword123!"
        })
        assert register_response.status_code == 201
        user_data = register_response.json()
        assert user_data["email"] == "testuser@example.com"
        logger.info("✅ User registration successful")
        
        # Step 2: User Login
        logger.info("\n2️⃣  Testing user login...")
        login_response = await client.post("/api/v1/auth/login", json={
            "email": "testuser@example.com",
            "password": "SecurePassword123!"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        access_token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.info("✅ User login successful")
        
        # Step 3: Add Polymarket API Keys
        logger.info("\n3️⃣  Testing API key addition...")
        api_key_response = await client.post(
            "/api/v1/settings/polymarket-keys",
            headers=headers,
            json={
                "api_key": "test_api_key_123",
                "api_secret": "test_api_secret_456"
            }
        )
        assert api_key_response.status_code in [200, 201]
        logger.info("✅ API keys added successfully")
        
        # Step 4: Browse Trader Leaderboard
        logger.info("\n4️⃣  Testing trader leaderboard...")
        leaderboard_response = await client.get(
            "/api/v1/traders/leaderboard?limit=10",
            headers=headers
        )
        assert leaderboard_response.status_code == 200
        traders = leaderboard_response.json()
        assert len(traders.get("traders", [])) > 0
        top_trader = traders["traders"][0]
        logger.info(f"✅ Found {len(traders['traders'])} traders")
        
        # Step 5: Create Copy Relationship
        logger.info("\n5️⃣  Testing copy relationship creation...")
        copy_response = await client.post(
            "/api/v1/copy-relationships",
            headers=headers,
            json={
                "trader_id": top_trader["id"],
                "copy_percentage": 1.0,
                "max_investment_usd": 100.0
            }
        )
        assert copy_response.status_code in [200, 201]
        copy_relationship = copy_response.json()
        logger.info("✅ Copy relationship created")
        
        # Step 6: View Dashboard
        logger.info("\n6️⃣  Testing dashboard access...")
        dashboard_response = await client.get(
            "/api/v1/dashboard",
            headers=headers
        )
        assert dashboard_response.status_code == 200
        dashboard = dashboard_response.json()
        assert "total_pnl" in dashboard
        assert "active_copies" in dashboard
        logger.info("✅ Dashboard accessed successfully")
        
        # Step 7: View User Copies
        logger.info("\n7️⃣  Testing copies list...")
        copies_response = await client.get(
            "/api/v1/copies",
            headers=headers
        )
        assert copies_response.status_code == 200
        copies = copies_response.json()
        assert len(copies.get("copies", [])) >= 1
        logger.info("✅ Copies retrieved successfully")
        
        # Step 8: Subscription Status
        logger.info("\n8️⃣  Testing subscription status...")
        subscription_response = await client.get(
            "/api/v1/subscription/status",
            headers=headers
        )
        assert subscription_response.status_code == 200
        subscription = subscription_response.json()
        assert subscription["tier"] == "FREE"
        logger.info("✅ Subscription status retrieved")
        
        logger.info("\n" + "="*60)
        logger.info("✅ COMPLETE USER JOURNEY TEST PASSED")
        logger.info("="*60)
