import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, SubscriptionTier
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate

@pytest.mark.asyncio
class TestAuthService:
    """Test authentication service"""
    
    async def test_register_new_user(self, db_session: AsyncSession):
        """Test user registration"""
        auth_service = AuthService(db_session)
        
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            password="TestPassword123!"
        )
        
        user = await auth_service.register_user(user_data)
        
        assert user is not None
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.hashed_password != "TestPassword123!"
        assert user.subscription_tier == SubscriptionTier.FREE
    
    async def test_register_duplicate_email(self, db_session: AsyncSession):
        """Test registration with duplicate email"""
        auth_service = AuthService(db_session)
        
        # Create first user
        user_data = UserCreate(
            email="test@example.com",
            username="testuser1",
            password="TestPassword123!"
        )
        await auth_service.register_user(user_data)
        
        # Try to create second user with same email
        user_data2 = UserCreate(
            email="test@example.com",
            username="testuser2",
            password="TestPassword123!"
        )
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await auth_service.register_user(user_data2)
    
    async def test_authenticate_valid_credentials(self, db_session: AsyncSession):
        """Test authentication with valid credentials"""
        auth_service = AuthService(db_session)
        
        # Register user
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            password="TestPassword123!"
        )
        await auth_service.register_user(user_data)
        
        # Authenticate
        user = await auth_service.authenticate_user("test@example.com", "TestPassword123!")
        
        assert user is not None
        assert user.email == "test@example.com"
    
    async def test_authenticate_invalid_password(self, db_session: AsyncSession):
        """Test authentication with invalid password"""
        auth_service = AuthService(db_session)
        
        # Register user
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            password="TestPassword123!"
        )
        await auth_service.register_user(user_data)
        
        # Try to authenticate with wrong password
        user = await auth_service.authenticate_user("test@example.com", "WrongPassword")
        
        assert user is None
    
    async def test_create_tokens(self, db_session: AsyncSession):
        """Test token creation"""
        auth_service = AuthService(db_session)
        
        # Register user
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            password="TestPassword123!"
        )
        user = await auth_service.register_user(user_data)
        
        # Create tokens
        tokens = auth_service.create_tokens(user)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
