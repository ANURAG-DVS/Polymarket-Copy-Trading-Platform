from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshTokenRequest
)
from app.services.auth_service import AuthService
from app.services.email_service import send_welcome_email
from app.models.user import User

router = APIRouter()

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    
    # Register user
    user = await auth_service.register_user(user_data)
    
    # Create tokens
    tokens = await auth_service.create_tokens(user)
    
    # Send welcome email (non-blocking)
    try:
        await send_welcome_email(user.email, user.username)
    except Exception as e:
        # Don't fail registration if email fails
        pass
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user=UserResponse.from_orm(user)
    )

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password"""
    auth_service = AuthService(db)
    
    # Authenticate user
    user = await auth_service.authenticate_user(login_data)
    
    # Create tokens
    tokens = await auth_service.create_tokens(user)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user=UserResponse.from_orm(user)
    )

@router.post("/refresh", response_model=dict)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    auth_service = AuthService(db)
    
    tokens = await auth_service.refresh_access_token(refresh_data.refresh_token)
    
    return tokens

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset"""
    auth_service = AuthService(db)
    
    await auth_service.forgot_password(forgot_data.email)
    
    return {"message": "If the email exists, a password reset link has been sent"}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password with token"""
    auth_service = AuthService(db)
    
    await auth_service.reset_password(reset_data.token, reset_data.new_password)
    
    return {"message": "Password has been reset successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse.from_orm(current_user)

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """Logout current user (client should discard tokens)"""
    # In a production system, you might want to blacklist the token
    return {"message": "Logged out successfully"}
