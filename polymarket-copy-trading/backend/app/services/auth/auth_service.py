"""
Authentication Service

Handles user authentication, JWT tokens, and security features.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
import bcrypt
import jwt
from loguru import logger

from app.core.config import settings


class AuthService:
    """
    Authentication service for user management and JWT tokens.
    
    Features:
    - Password hashing with bcrypt
    - JWT access + refresh tokens
    - Email verification tokens
    - Password reset tokens
    - Login attempt tracking
    """
    
    # Token expiry times
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    VERIFICATION_TOKEN_EXPIRE_HOURS = 24
    RESET_TOKEN_EXPIRE_HOURS = 1
    
    # Security
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    def __init__(self):
        """Initialize auth service"""
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Bcrypt hash
            
        Returns:
            True if password matches
        """
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    def validate_password_strength(self, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validate password meets complexity requirements.
        
        Requirements:
        - At least 8 characters
        - Contains uppercase letter
        - Contains lowercase letter
        - Contains digit
        - Contains special character
        
        Returns:
            (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain digit"
        
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain special character"
        
        return True, None
    
    def create_access_token(self, user_id: int, email: str) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User ID
            email: User email
            
        Returns:
            JWT token string
        """
        expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def create_refresh_token(self, user_id: int) -> str:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User ID
            
        Returns:
            JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload = {
            "user_id": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(32)  # Unique token ID
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[dict]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            token_type: "access" or "refresh"
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def create_verification_token(self, user_id: int, email: str) -> str:
        """
        Create email verification token.
        
        Args:
            user_id: User ID
            email: User email
            
        Returns:
            Verification token
        """
        expire = datetime.utcnow() + timedelta(hours=self.VERIFICATION_TOKEN_EXPIRE_HOURS)
        
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "email_verification",
            "exp": expire
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def create_password_reset_token(self, user_id: int, email: str) -> str:
        """
        Create password reset token.
        
        Args:
            user_id: User ID
            email: User email
            
        Returns:
            Reset token
        """
        expire = datetime.utcnow() + timedelta(hours=self.RESET_TOKEN_EXPIRE_HOURS)
        
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "password_reset",
            "exp": expire,
            "nonce": secrets.token_urlsafe(16)  # One-time use
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_special_token(
        self,
        token: str,
        token_type: str
    ) -> Optional[dict]:
        """
        Verify verification or reset token.
        
        Args:
            token: JWT token
            token_type: "email_verification" or "password_reset"
            
        Returns:
            Decoded payload or None
        """
        return self.verify_token(token, token_type)


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get singleton instance of AuthService"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
