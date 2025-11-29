import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    verify_password,
    generate_password_reset_token
)
from app.core.config import settings

class TestJWTTokens:
    """Test JWT token creation and verification"""
    
    def test_create_access_token(self):
        """Test access token creation"""
        payload = {"sub": "test@example.com", "user_id": 1}
        token = create_access_token(payload)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        payload = {"sub": "test@example.com"}
        token = create_refresh_token(payload)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_valid_token(self):
        """Test verification of valid token"""
        payload = {"sub": "test@example.com", "user_id": 1}
        token = create_access_token(payload)
        
        decoded = verify_token(token, settings.JWT_SECRET)
        
        assert decoded is not None
        assert decoded["sub"] == "test@example.com"
        assert decoded["user_id"] == 1
    
    def test_verify_invalid_token(self):
        """Test verification of invalid token"""
        invalid_token = "invalid.token.here"
        
        decoded = verify_token(invalid_token, settings.JWT_SECRET)
        
        assert decoded is None
    
    def test_verify_token_wrong_secret(self):
        """Test verification with wrong secret"""
        payload = {"sub": "test@example.com"}
        token = create_access_token(payload)
        
        decoded = verify_token(token, "wrong_secret")
        
        assert decoded is None

class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_correct_password(self):
        """Test verification of correct password"""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_incorrect_password(self):
        """Test verification of incorrect password"""
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        assert verify_password("WrongPassword", hashed) is False
    
    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes"""
        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2  # Salt makes them different

class TestPasswordResetToken:
    """Test password reset token generation"""
    
    def test_generate_reset_token(self):
        """Test reset token generation"""
        token = generate_password_reset_token()
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) == 32  # 32 hex characters
    
    def test_unique_reset_tokens(self):
        """Test that tokens are unique"""
        token1 = generate_password_reset_token()
        token2 = generate_password_reset_token()
        
        assert token1 != token2
