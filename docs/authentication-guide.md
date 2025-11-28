# Authentication System - Usage Guide

## Overview

Production-ready authentication system with modern security features:
- ✅ JWT access + refresh tokens
- ✅ Bcrypt password hashing
- ✅ Email verification
- ✅ Password reset flow
- ✅ Account lockout protection
- ✅ httpOnly cookies for refresh tokens
- ✅ Rate limiting ready

## Quick Start

### 1. Register New User

```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "username": "trader123"
}
```

**Password Requirements:**
- Minimum 8 characters
- Contains uppercase letter
- Contains lowercase letter
- Contains digit
- Contains special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

**Response (201 Created):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "trader123",
  "email_verified": false,
  "created_at": "2024-01-15T10:30:00"
}
```

### 2. Login

```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email_or_username": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Note:** Refresh token set as httpOnly cookie automatically.

### 3. Access Protected Routes

```bash
GET /api/v1/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "trader123",
  "email_verified": true,
  "created_at": "2024-01-15T10:30:00"
}
```

## Token Management

### Access Token

- **Expiry**: 15 minutes
- **Usage**: Include in Authorization header
- **Format**: `Authorization: Bearer <token>`

### Refresh Token

- **Expiry**: 7 days
- **Storage**: httpOnly cookie (automatic)
- **Security**: Cannot be accessed by JavaScript

### Refresh Access Token

```bash
POST /api/v1/auth/refresh
Cookie: refresh_token=<token>
```

**Response:**
```json
{
  "access_token": "new_token_here...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Auto-refresh Pattern (Frontend):**
```javascript
async function apiCall(url, options = {}) {
  let response = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${getAccessToken()}`,
      ...options.headers
    }
  });
  
  // If 401, try refreshing token
  if (response.status === 401) {
    const refreshed = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include'  // Send cookies
    });
    
    if (refreshed.ok) {
      const { access_token } = await refreshed.json();
      setAccessToken(access_token);
      
      // Retry original request
      response = await fetch(url, {
        ...options,
        headers: {
          'Authorization': `Bearer ${access_token}`,
          ...options.headers
        }
      });
    }
  }
  
  return response;
}
```

## Email Verification

### Verify Email

```bash
POST /api/v1/auth/verify-email?token=<verification_token>
```

**Response:**
```json
{
  "message": "Email verified successfully"
}
```

**Frontend Integration:**
```javascript
// In email verification page
const params = new URLSearchParams(window.location.search);
const token = params.get('token');

await fetch(`/api/v1/auth/verify-email?token=${token}`, {
  method: 'POST'
});
```

## Password Reset

### Request Reset

```bash
POST /api/v1/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "If email exists, reset link has been sent"
}
```

**Note:** Always returns success to prevent email enumeration.

### Confirm Reset

```bash
POST /api/v1/auth/reset-password
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "new_password": "NewSecurePass456!"
}
```

**Response:**
```json
{
  "message": "Password reset successfully"
}
```

## Security Features

### Account Lockout

**Protection:**
- Max 5 failed login attempts
- 30-minute lockout after exceeding limit
- Counter resets on successful login

**Locked Account Response (403):**
```json
{
  "detail": "Account locked until 2024-01-15T11:00:00"
}
```

### Password Validation

```python
from app.services.auth import get_auth_service

auth = get_auth_service()

is_valid, error = auth.validate_password_strength("weak")
# Returns: (False, "Password must be at least 8 characters")

is_valid, error = auth.validate_password_strength("SecurePass123!")
# Returns: (True, None)
```

### Protected Routes

Use `get_current_user` dependency:

```python
from fastapi import Depends
from app.api.v1.endpoints.auth import get_current_user
from app.models.api_key import User

@router.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id}
```

## Logout

```bash
POST /api/v1/auth/logout
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**Note:** Clears refresh token cookie. Access tokens remain valid until expiry (15 min).

## Environment Variables

Add to `.env`:

```bash
# JWT Secret (generate with: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here

# Token expiry (optional, defaults applied)
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Error Handling

### Common Errors

**400 Bad Request** - Invalid input
```json
{
  "detail": "Email already registered"
}
```

**401 Unauthorized** - Invalid credentials
```json
{
  "detail": "Invalid credentials"
}
```

**403 Forbidden** - Account locked
```json
{
  "detail": "Account locked until 2024-01-15T11:00:00"
}
```

**422 Validation Error** - Pydantic validation failed
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

## Testing

### Python (pytest)

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "username": "testuser"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["email_verified"] == False

@pytest.mark.asyncio
async def test_login():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email_or_username": "test@example.com",
            "password": "SecurePass123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
```

## Production Checklist

- [ ] Set strong `SECRET_KEY` in environment
- [ ] Enable HTTPS only (secure cookies)
- [ ] Configure email service (SMTP)
- [ ] Set up Redis for token blacklist
- [ ] Enable rate limiting on /auth endpoints
- [ ] Monitor failed login attempts
- [ ] Set up audit logging
- [ ] Configure 2FA (optional)

## Next Steps

1. **Email Integration**: Connect email service for verification/reset
2. **Token Blacklist**: Implement Redis blacklist for logout
3. **2FA**: Add TOTP support with PyOTP
4. **Session Management**: Track and revoke active sessions
5. **Audit Logging**: Log all auth events for security

## Best Practices

1. **Store tokens securely**:
   - Access token: Memory only (not localStorage)
   - Refresh token: httpOnly cookie (automatic)

2. **Handle token expiry**:
   - Refresh access token before making API calls
   - Log out user if refresh fails

3. **Validate on backend**:
   - Never trust client-side validation
   - Always verify tokens on protected routes

4. **Password security**:
   - Never log passwords
   - Use bcrypt for hashing (built-in)
   - Enforce strong password policy

5. **Rate limiting**:
   - Limit registration attempts
   - Limit login attempts (built-in lockout)
   - Limit password reset requests
