"""
Authentication Endpoints

User registration, login, token refresh, password reset, and email verification.
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, EmailStr, Field
import redis.asyncio as redis

from app.db.session import get_db
from app.models.api_key import User
from app.services.auth.auth_service import get_auth_service
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


# ============================================================================
# Request/Response Models
# ============================================================================

class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    username: Optional[str] = Field(None, min_length=3, max_length=50)


class LoginRequest(BaseModel):
    """Login request"""
    email_or_username: str
    password: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset"""
    token: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User info response"""
    id: int
    email: str
    username: Optional[str]
    email_verified: bool
    created_at: datetime


# ============================================================================
# Helper Functions
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token.
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    auth_service = get_auth_service()
    
    # Extract token
    token = credentials.credentials
    
    # Verify token
    payload = auth_service.verify_token(token, "access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get user
    user_id = payload.get("user_id")
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


async def check_token_blacklist(token: str) -> bool:
    """Check if token is blacklisted"""
    # In production, check Redis blacklist
    # For now, return False
    return False


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    **Requirements:**
    - Valid email address
    - Password: min 8 chars, uppercase, lowercase, digit, special char
    - Username: optional, 3-50 chars
    
    **Response:**
    - User details (email verification required before trading)
    
    **Example:**
    ```json
    {
      "email": "user@example.com",
      "password": "SecurePass123!",
      "username": "trader123"
    }
    ```
    """
    auth_service = get_auth_service()
    
    # Validate password strength
    is_valid, error_msg = auth_service.validate_password_strength(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Check if email already exists
    query = select(User).where(User.email == request.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check username if provided
    if request.username:
        query = select(User).where(User.username == request.username)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Hash password
    hashed_password = auth_service.hash_password(request.password)
    
    # Create user
    new_user = User(
        email=request.email,
        username=request.username,
        password_hash=hashed_password,
        email_verified=False,
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Generate verification token
    verification_token = auth_service.create_verification_token(
        new_user.id,
        new_user.email
    )
    
    # TODO: Send verification email
    # await send_verification_email(new_user.email, verification_token)
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        email_verified=new_user.email_verified,
        created_at=new_user.created_at
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Login and receive JWT tokens.
    
    **Input:**
    - email_or_username: Email address or username
    - password: User password
    
    **Response:**
    - Access token (15 min expiry)
    - Refresh token (httpOnly cookie, 7 days)
    
    **Example:**
    ```json
    {
      "email_or_username": "user@example.com",
      "password": "SecurePass123!"
    }
    ```
    """
    auth_service = get_auth_service()
    
    # Find user by email or username
    query = select(User).where(
        (User.email == request.email_or_username) |
        (User.username == request.email_or_username)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check account lockout
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked until {user.locked_until.isoformat()}"
        )
    
    # Verify password
    if not auth_service.verify_password(request.password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        
        # Lock account if too many failures
        if user.failed_login_attempts >= auth_service.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(
                minutes=auth_service.LOCKOUT_DURATION_MINUTES
            )
        
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = auth_service.create_refresh_token(user.id)
    
    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # HTTPS only in production
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token from cookie.
    
    **Response:**
    - New access token
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )
    
    auth_service = get_auth_service()
    
    # Verify refresh token
    payload = auth_service.verify_token(refresh_token, "refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Check token blacklist
    if await check_token_blacklist(refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )
    
    # Get user
    user_id = payload.get("user_id")
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new access token
    access_token = auth_service.create_access_token(user.id, user.email)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing refresh token cookie.
    
    **Note:** Access tokens remain valid until expiry (15 min).
    For immediate invalidation, implement token blacklist.
    """
    # Clear refresh token cookie
    response.delete_cookie("refresh_token")
    
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset email.
    
    **Input:**
    - email: User's email address
    
    **Response:**
    - Success message (always returns success for security)
    """
    auth_service = get_auth_service()
    
    # Find user
    query = select(User).where(User.email == request.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If email exists, reset link has been sent"}
    
    # Generate reset token
    reset_token = auth_service.create_password_reset_token(user.id, user.email)
    
    # TODO: Send reset email
    # await send_password_reset_email(user.email, reset_token)
    
    return {"message": "If email exists, reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password with token.
    
    **Input:**
    - token: Reset token from email
    - new_password: New password (min 8 chars, complexity required)
    """
    auth_service = get_auth_service()
    
    # Verify token
    payload = auth_service.verify_special_token(request.token, "password_reset")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Validate new password
    is_valid, error_msg = auth_service.validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Get user
    user_id = payload.get("user_id")
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Hash new password
    new_hash = auth_service.hash_password(request.new_password)
    
    # Update password
    user.password_hash = new_hash
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()
    
    return {"message": "Password reset successfully"}


@router.post("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email address with token.
    
    **Query Parameter:**
    - token: Verification token from email
    """
    auth_service = get_auth_service()
    
    # Verify token
    payload = auth_service.verify_special_token(token, "email_verification")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Get user
    user_id = payload.get("user_id")
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Mark email as verified
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Email verified successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's information.
    
    **Requires:** Valid access token in Authorization header
    
    **Example:**
    ```
    Authorization: Bearer <access_token>
    ```
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at
    )
