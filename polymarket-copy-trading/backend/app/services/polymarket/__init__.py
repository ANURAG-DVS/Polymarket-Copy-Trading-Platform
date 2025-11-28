"""
Polymarket API Client Package

Comprehensive wrapper for Polymarket's CLOB (Central Limit Order Book) API.
"""

from app.services.polymarket.client import PolymarketClient, get_polymarket_client
from app.services.polymarket.models import (
    Market,
    OrderBook,
    Position,
    TradeResult,
    MarketPrices,
    Balance,
    OrderStatus
)
from app.services.polymarket.errors import (
    PolymarketAPIError,
    AuthenticationError,
    RateLimitError,
    InsufficientFundsError,
    MarketClosedError,
    InvalidOrderError,
    NetworkError,
    ErrorCategory
)

__all__ = [
    # Client
    'PolymarketClient',
    'get_polymarket_client',
    
    # Models
    'Market',
    'OrderBook',
    'Position',
    'TradeResult',
    'MarketPrices',
    'Balance',
    'OrderStatus',
    
    # Errors
    'PolymarketAPIError',
    'AuthenticationError',
    'RateLimitError',
    'InsufficientFundsError',
    'MarketClosedError',
    'InvalidOrderError',
    'NetworkError',
    'ErrorCategory',
]
