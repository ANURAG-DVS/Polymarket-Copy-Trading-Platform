import httpx
from typing import Optional
from bot.config import config
import logging

logger = logging.getLogger(__name__)

class APIClient:
    """HTTP client for backend API"""
    
    def __init__(self):
        self.base_url = config.BACKEND_API_URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def register_telegram_user(self, telegram_id: int, username: str) -> dict:
        """Register new user via Telegram"""
        try:
            response = await self.client.post(
                f"{self.base_url}/auth/register",
                json={
                    "email": f"telegram_{telegram_id}@temp.com",
                    "username": username or f"telegram_{telegram_id}",
                    "password": f"telegram_auto_{telegram_id}"  # Auto-generated
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Get user by telegram ID"""
        try:
            # This would need a backend endpoint
            # For now, returning None
            return None
        except Exception as e:
            logger.error(f"Get user failed: {e}")
            return None
    
    async def get_traders_leaderboard(self, limit: int = 10) -> dict:
        """Get top traders"""
        try:
            response = await self.client.get(
                f"{self.base_url}/traders/leaderboard",
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get leaderboard failed: {e}")
            raise
    
    async def get_dashboard(self, token: str) -> dict:
        """Get user dashboard"""
        try:
            response = await self.client.get(
                f"{self.base_url}/dashboard",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get dashboard failed: {e}")
            raise
    
    async def get_copy_relationships(self, token: str) -> dict:
        """Get user's copy relationships"""
        try:
            response = await self.client.get(
                f"{self.base_url}/copy-relationships",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get copies failed: {e}")
            raise

# Global API client instance
api_client = APIClient()
