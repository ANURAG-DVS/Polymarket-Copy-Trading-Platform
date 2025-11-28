"""
Polymarket API Client - Error Classes

Comprehensive error handling for Polymarket API interactions.
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(str, Enum):
    """Categories of errors that can occur"""
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    MARKET_CLOSED = "market_closed"
    INVALID_ORDER = "invalid_order"
    NETWORK = "network"
    API_ERROR = "api_error"
    UNKNOWN = "unknown"


class PolymarketAPIError(Exception):
    """Base exception for all Polymarket API errors"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = status_code
        self.response_data = response_data or {}
        self.retry_after = retry_after
    
    def __str__(self):
        return f"[{self.category.value}] {self.message}"
    
    def is_retryable(self) -> bool:
        """Check if this error should trigger a retry"""
        return self.category in [
            ErrorCategory.NETWORK,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.API_ERROR
        ]


class AuthenticationError(PolymarketAPIError):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            **kwargs
        )


class RateLimitError(PolymarketAPIError):
    """Raised when rate limit is exceeded"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            retry_after=retry_after,
            **kwargs
        )


class InsufficientFundsError(PolymarketAPIError):
    """Raised when user has insufficient funds"""
    
    def __init__(self, message: str = "Insufficient funds", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.INSUFFICIENT_FUNDS,
            **kwargs
        )


class MarketClosedError(PolymarketAPIError):
    """Raised when trying to trade on a closed market"""
    
    def __init__(self, message: str = "Market is closed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.MARKET_CLOSED,
            **kwargs
        )


class InvalidOrderError(PolymarketAPIError):
    """Raised when order parameters are invalid"""
    
    def __init__(self, message: str = "Invalid order parameters", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.INVALID_ORDER,
            **kwargs
        )


class NetworkError(PolymarketAPIError):
    """Raised when network request fails"""
    
    def __init__(self, message: str = "Network request failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            **kwargs
        )


def categorize_error(
    status_code: Optional[int],
    response: Optional[Dict[str, Any]]
) -> ErrorCategory:
    """
    Categorize error based on HTTP status code and response.
    
    Args:
        status_code: HTTP status code
        response: API response dictionary
        
    Returns:
        ErrorCategory enum value
    """
    if status_code == 401 or status_code == 403:
        return ErrorCategory.AUTHENTICATION
    
    if status_code == 429:
        return ErrorCategory.RATE_LIMIT
    
    if status_code == 400 and response:
        error_msg = str(response.get('error', '')).lower()
        
        if 'insufficient' in error_msg or 'balance' in error_msg:
            return ErrorCategory.INSUFFICIENT_FUNDS
        
        if 'closed' in error_msg or 'inactive' in error_msg:
            return ErrorCategory.MARKET_CLOSED
        
        if 'invalid' in error_msg or 'order' in error_msg:
            return ErrorCategory.INVALID_ORDER
    
    if status_code and status_code >= 500:
        return ErrorCategory.API_ERROR
    
    if status_code and status_code >= 400:
        return ErrorCategory.API_ERROR
    
    return ErrorCategory.UNKNOWN
