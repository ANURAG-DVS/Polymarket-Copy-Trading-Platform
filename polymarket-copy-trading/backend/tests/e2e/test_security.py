import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

@pytest.mark.e2e
@pytest.mark.asyncio
class TestSecurityAudit:
    """Security audit tests"""
    
    async def test_unauthorized_access(self, client: AsyncClient):
        """Test that endpoints require authentication"""
        
        logger.info("\n🔒 Testing: Unauthorized Access Prevention")
        
        # Try to access protected endpoints without auth
        endpoints = [
            "/api/v1/dashboard",
            "/api/v1/copies",
            "/api/v1/traders/leaderboard",
            "/api/v1/subscription/status"
        ]
        
        for endpoint in endpoints:
            response = await client.get(endpoint)
            assert response.status_code in [401, 403], \
                f"Endpoint {endpoint} should require authentication"
        
        logger.info("✅ All protected endpoints require authentication")
    
    async def test_user_data_isolation(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test that users can only access their own data"""
        
        logger.info("\n🔒 Testing: User Data Isolation")
        
        # Create two users
        user1_response = await client.post("/api/v1/auth/register", json={
            "email": "user1@example.com",
            "username": "user1",
            "password": "Password123!"
        })
        
        user2_response = await client.post("/api/v1/auth/register", json={
            "email": "user2@example.com",
            "username": "user2",
            "password": "Password123!"
        })
        
        # Login as user1
        login1 = await client.post("/api/v1/auth/login", json={
            "email": "user1@example.com",
            "password": "Password123!"
        })
        user1_token = login1.json()["access_token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}
        
        # Login as user2
        login2 = await client.post("/api/v1/auth/login", json={
            "email": "user2@example.com",
            "password": "Password123!"
        })
        user2_token = login2.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}
        
        # Get user1's data
        user1_dashboard = await client.get(
            "/api/v1/dashboard",
            headers=user1_headers
        )
        
        # Get user2's data
        user2_dashboard = await client.get(
            "/api/v1/dashboard",
            headers=user2_headers
        )
        
        # Data should be different
        assert user1_dashboard.json() != user2_dashboard.json() or \
               (user1_dashboard.json() == user2_dashboard.json() and 
                len(user1_dashboard.json()) == 0)
        
        logger.info("✅ User data properly isolated")
    
    async def test_sql_injection_prevention(
        self,
        client: AsyncClient, 
        auth_headers: dict
    ):
        """Test SQL injection prevention"""
        
        logger.info("\n🔒 Testing: SQL Injection Prevention")
        
        # Try SQL injection in various parameters
        sql_payloads = [
            "1' OR '1'='1",
            "'; DROP TABLE users--",
            "1; DELETE FROM trades WHERE 1=1--"
        ]
        
        for payload in sql_payloads:
            # Try in query parameters
            response = await client.get(
                f"/api/v1/traders/{payload}",
                headers=auth_headers
            )
            
            # Should return 404 or 422, not 500 (which would indicate SQL error)
            assert response.status_code in [404, 422], \
                f"SQL injection payload not properly handled: {payload}"
        
        logger.info("✅ SQL injection attempts blocked")
    
    async def test_xss_prevention(self, client: AsyncClient):
        """Test XSS prevention in user inputs"""
        
        logger.info("\n🔒 Testing: XSS Prevention")
        
        # Try to register with XSS payload in username
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>"
        ]
        
        for payload in xss_payloads:
            response = await client.post("/api/v1/auth/register", json={
                "email": f"test{hash(payload)}@example.com",
                "username": payload,
                "password": "Password123!"
            })
            
            # Should either be rejected or sanitized
            if response.status_code == 201:
                data = response.json()
                # Username should not contain script tags
                assert "<script>" not in data.get("username", "")
                assert "javascript:" not in data.get("username", "")
        
        logger.info("✅ XSS payloads handled safely")
    
    async def test_password_security(self, client: AsyncClient):
        """Test password security requirements"""
        
        logger.info("\n🔒 Testing: Password Security")
        
        weak_passwords = ["123", "password", "abc", "test"]
        
        for weak_pass in weak_passwords:
            response = await client.post("/api/v1/auth/register", json={
                "email": f"test{hash(weak_pass)}@example.com",
                "username": f"user{hash(weak_pass)}",
                "password": weak_pass
            })
            
            # Weak passwords should be rejected
            assert response.status_code == 422, \
                f"Weak password '{weak_pass}' should be rejected"
        
        logger.info("✅ Password requirements enforced")
    
    async def test_sensitive_data_exposure(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test that sensitive data is not exposed in responses"""
        
        logger.info("\n🔒 Testing: Sensitive Data Exposure Prevention")
        
        # Get user profile
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Should not contain sensitive fields
            assert "password" not in data
            assert "hashed_password" not in data
            assert "api_secret" not in data
            
            logger.info("✅ Sensitive data not exposed in API responses")
