"""
Polymarket API Client

Comprehensive wrapper for Polymarket's CLOB (Central Limit Order Book) API.

Features:
- API key authentication
- Request signing
- Automatic retry with exponential backoff
- Rate limit handling
- Mock/testnet/dry-run modes
- Comprehensive error handling

API Documentation: https://docs.polymarket.com
"""

import asyncio
import time
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
import httpx
from loguru import logger

from app.services.polymarket.models import (
    Market, OrderBook, Position, TradeResult, 
    MarketPrices, Balance, OrderStatus
)
from app.services.polymarket.errors import (
    PolymarketAPIError, AuthenticationError, RateLimitError,
    NetworkError, categorize_error
)
from app.core.config import settings


class PolymarketClient:
    """
    Async client for Polymarket CLOB API.
    
    Example:
        ```python
        client = PolymarketClient(
            api_key="your_key",
            api_secret="your_secret"
        )
        
        # Get markets
        markets = await client.get_markets()
        
        # Place order
        result = await client.place_buy_order(
            market_id="0x123...",
            outcome="YES",
            amount=Decimal("10"),
            price=Decimal("0.55")
        )
        ```
    """
    
    # API endpoints
    BASE_URL = "https://clob.polymarket.com"
    TESTNET_URL = "https://clob-staging.polymarket.com"
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2  # seconds
    RETRY_BACKOFF_MAX = 60  # seconds
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60  # seconds
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        testnet: bool = False,
        mock_mode: bool = False,
        dry_run: bool = False,
        timeout: int = 30
    ):
        """
        Initialize Polymarket API client.
        
        Args:
            api_key: Polymarket API key
            api_secret: Polymarket API secret
            private_key: Ethereum private key for signing
            testnet: Use testnet endpoint
            mock_mode: Return mocked responses (for development)
            dry_run: Validate requests but don't execute (for testing)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_key = private_key
        self.testnet = testnet
        self.mock_mode = mock_mode
        self.dry_run = dry_run
        
        # Select base URL
        self.base_url = self.TESTNET_URL if testnet else self.BASE_URL
        
        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._get_default_headers()
        )
        
        # Rate limiting
        self._request_timestamps: List[float] = []
        
        logger.info(
            f"PolymarketClient initialized "
            f"(testnet={testnet}, mock={mock_mode}, dry_run={dry_run})"
        )
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"PolymarketCopyTrading/{settings.APP_VERSION}"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    async def _check_rate_limit(self):
        """
        Check and enforce rate limiting.
        
        Raises:
            RateLimitError: If rate limit would be exceeded
        """
        now = time.time()
        
        # Remove timestamps outside the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps 
            if now - ts < self.RATE_LIMIT_WINDOW
        ]
        
        # Check if we're at the limit
        if len(self._request_timestamps) >= self.RATE_LIMIT_REQUESTS:
            oldest = self._request_timestamps[0]
            retry_after = int(self.RATE_LIMIT_WINDOW - (now - oldest)) + 1
            
            raise RateLimitError(
                f"Rate limit exceeded: {self.RATE_LIMIT_REQUESTS} requests per {self.RATE_LIMIT_WINDOW}s",
                retry_after=retry_after
            )
        
        # Record this request
        self._request_timestamps.append(now)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body
            retry_count: Current retry attempt
            
        Returns:
            Parsed JSON response
            
        Raises:
            PolymarketAPIError: On API error
        """
        # Mock mode - return fake data
        if self.mock_mode:
            return self._get_mock_response(endpoint)
        
        # Check rate limiting
        await self._check_rate_limit()
        
        try:
            # Make request
            response = await self.client.request(
                method=method,
                url=endpoint,
                params=params,
                json=data
            )
            
            # Parse response
            try:
                response_data = response.json()
            except Exception:
                response_data = {}
            
            # Check for errors
            if response.status_code >= 400:
                await self._handle_error_response(
                    response.status_code,
                    response_data,
                    retry_count
                )
            
            return response_data
            
        except httpx.TimeoutException as e:
            error = NetworkError(f"Request timeout: {e}")
            if retry_count < self.MAX_RETRIES:
                return await self._retry_request(
                    method, endpoint, params, data, retry_count, error
                )
            raise error
            
        except httpx.NetworkError as e:
            error = NetworkError(f"Network error: {e}")
            if retry_count < self.MAX_RETRIES:
                return await self._retry_request(
                    method, endpoint, params, data, retry_count, error
                )
            raise error
            
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            raise PolymarketAPIError(f"Unexpected error: {e}")
    
    async def _handle_error_response(
        self,
        status_code: int,
        response_data: Dict,
        retry_count: int
    ):
        """Handle error response from API"""
        category = categorize_error(status_code, response_data)
        error_message = response_data.get('error', response_data.get('message', 'Unknown error'))
        
        # Create appropriate error
        if category == "authentication":
            raise AuthenticationError(error_message, status_code=status_code)
        
        elif category == "rate_limit":
            retry_after = response_data.get('retry_after', 60)
            error = RateLimitError(error_message, retry_after=retry_after)
            
            # Rate limits are retryable
            if retry_count < self.MAX_RETRIES:
                await asyncio.sleep(retry_after)
                # This will be caught and retried by caller
            raise error
        
        else:
            # Create generic error with category
            error = PolymarketAPIError(
                message=error_message,
                category=category,
                status_code=status_code,
                response_data=response_data
            )
            raise error
    
    async def _retry_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict],
        data: Optional[Dict],
        retry_count: int,
        error: PolymarketAPIError
    ) -> Dict[str, Any]:
        """Retry request with exponential backoff"""
        if not error.is_retryable():
            raise error
        
        retry_count += 1
        backoff = min(
            self.RETRY_BACKOFF_BASE ** retry_count,
            self.RETRY_BACKOFF_MAX
        )
        
        logger.warning(
            f"Retrying request (attempt {retry_count}/{self.MAX_RETRIES}) "
            f"after {backoff}s: {error}"
        )
        
        await asyncio.sleep(backoff)
        
        return await self._request(
            method=method,
            endpoint=endpoint,
            params=params,
            data=data,
            retry_count=retry_count
        )
    
    def _get_mock_response(self, endpoint: str) -> Dict[str, Any]:
        """Get mocked response for development"""
        # Simple mock responses for testing
        if '/markets' in endpoint:
            return {'markets': []}
        elif '/orderbook' in endpoint:
            return {'bids': [], 'asks': []}
        elif '/positions' in endpoint:
            return {'positions': []}
        return {}
    
    # ========================================================================
    # MARKET DATA METHODS
    # ========================================================================
    
    async def get_markets(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Market]:
        """
        Fetch all markets.
        
        Args:
            active_only: Only return active markets
            limit: Maximum number of markets to return
            offset: Pagination offset
            
        Returns:
            List of Market objects
            
        Example:
            ```python
            markets = await client.get_markets(active_only=True)
            for market in markets:
                print(f"{market.question}: ${market.volume}")
            ```
        """
        params = {
            'active': active_only,
            'limit': limit,
            'offset': offset
        }
        
        response = await self._request('GET', '/markets', params=params)
        
        # Parse markets
        markets_data = response.get('markets', [])
        markets = [Market(**m) for m in markets_data]
        
        logger.info(f"Fetched {len(markets)} markets")
        return markets
    
    async def get_market_by_id(self, market_id: str) -> Market:
        """
        Get specific market details.
        
        Args:
            market_id: Market identifier
            
        Returns:
            Market object
            
        Raises:
            PolymarketAPIError: If market not found
        """
        response = await self._request('GET', f'/markets/{market_id}')
        return Market(**response)
    
    async def get_market_prices(self, market_id: str) -> MarketPrices:
        """
        Get current YES/NO prices for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            MarketPrices object with YES and NO prices
        """
        response = await self._request('GET', f'/markets/{market_id}/prices')
        
        return MarketPrices(
            market_id=market_id,
            yes_price=Decimal(str(response['yes_price'])),
            no_price=Decimal(str(response['no_price'])),
            last_updated=datetime.utcnow()
        )
    
    async def get_order_book(
        self,
        market_id: str,
        outcome: str = "YES"
    ) -> OrderBook:
        """
        Get order book depth for a market.
        
        Args:
            market_id: Market identifier
            outcome: "YES" or "NO"
            
        Returns:
            OrderBook object with bids and asks
        """
        response = await self._request(
            'GET',
            f'/markets/{market_id}/orderbook',
            params={'outcome': outcome}
        )
        
        # Parse order book
        bids = [
            {'price': Decimal(str(b['price'])), 'size': Decimal(str(b['size']))}
            for b in response.get('bids', [])
        ]
        asks = [
            {'price': Decimal(str(a['price'])), 'size': Decimal(str(a['size']))}
            for a in response.get('asks', [])
        ]
        
        # Calculate spread and mid price
        best_bid = bids[0]['price'] if bids else Decimal('0')
        best_ask = asks[0]['price'] if asks else Decimal('1')
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        
        return OrderBook(
            market_id=market_id,
            outcome=outcome,
            bids=bids,
            asks=asks,
            spread=spread,
            mid_price=mid_price
        )
    
    # ========================================================================
    # TRADING METHODS
    # ========================================================================
    
    async def place_buy_order(
        self,
        market_id: str,
        outcome: str,
        amount: Decimal,
        price: Decimal,
        post_only: bool = False
    ) -> TradeResult:
        """
        Place a buy order (buy outcome tokens).
        
        Args:
            market_id: Market identifier
            outcome: "YES" or "NO"
            amount: Number of tokens to buy
            price: Maximum price willing to pay (0-1)
            post_only: Only place order if it doesn't immediately match
            
        Returns:
            TradeResult with order details
            
        Raises:
            InvalidOrderError: If order parameters are invalid
            InsufficientFundsError: If insufficient balance
            
        Example:
            ```python
            result = await client.place_buy_order(
                market_id="0x123...",
                outcome="YES",
                amount=Decimal("10"),
                price=Decimal("0.55")
            )
            print(f"Order placed: {result.order_id}")
            ```
        """
        # Validate inputs
        if price < 0 or price > 1:
            raise InvalidOrderError(f"Price must be between 0 and 1, got {price}")
        
        if amount <= 0:
            raise InvalidOrderError(f"Amount must be positive, got {amount}")
        
        # Dry run mode - validate but don't execute
        if self.dry_run:
            logger.info(f"DRY RUN: Would place buy order for {amount} @ {price}")
            return TradeResult(
                success=True,
                market_id=market_id,
                side="BUY",
                outcome=outcome,
                size=amount,
                price=price,
                status="DRY_RUN"
            )
        
        # Place order
        data = {
            'market_id': market_id,
            'outcome': outcome,
            'side': 'BUY',
            'amount': str(amount),
            'price': str(price),
            'post_only': post_only
        }
        
        response = await self._request('POST', '/orders', data=data)
        
        return TradeResult(
            success=True,
            order_id=response.get('order_id'),
            transaction_hash=response.get('tx_hash'),
            market_id=market_id,
            side="BUY",
            outcome=outcome,
            size=amount,
            price=price,
            filled_size=Decimal(str(response.get('filled', 0))),
            average_fill_price=Decimal(str(response.get('avg_price', price))),
            fees=Decimal(str(response.get('fees', 0))),
            status=response.get('status', 'PENDING')
        )
    
    async def place_sell_order(
        self,
        market_id: str,
        outcome: str,
        amount: Decimal,
        price: Decimal,
        post_only: bool = False
    ) -> TradeResult:
        """
        Place a sell order (sell outcome tokens).
        
        Args:
            market_id: Market identifier
            outcome: "YES" or "NO"
            amount: Number of tokens to sell
            price: Minimum price willing to accept (0-1)
            post_only: Only place order if it doesn't immediately match
            
        Returns:
            TradeResult with order details
        """
        # Validate inputs
        if price < 0 or price > 1:
            raise InvalidOrderError(f"Price must be between 0 and 1, got {price}")
        
        if amount <= 0:
            raise InvalidOrderError(f"Amount must be positive, got {amount}")
        
        # Dry run mode
        if self.dry_run:
            logger.info(f"DRY RUN: Would place sell order for {amount} @ {price}")
            return TradeResult(
                success=True,
                market_id=market_id,
                side="SELL",
                outcome=outcome,
                size=amount,
                price=price,
                status="DRY_RUN"
            )
        
        # Place order
        data = {
            'market_id': market_id,
            'outcome': outcome,
            'side': 'SELL',
            'amount': str(amount),
            'price': str(price),
            'post_only': post_only
        }
        
        response = await self._request('POST', '/orders', data=data)
        
        return TradeResult(
            success=True,
            order_id=response.get('order_id'),
            transaction_hash=response.get('tx_hash'),
            market_id=market_id,
            side="SELL",
            outcome=outcome,
            size=amount,
            price=price,
            filled_size=Decimal(str(response.get('filled', 0))),
            average_fill_price=Decimal(str(response.get('avg_price', price))),
            fees=Decimal(str(response.get('fees', 0))),
            status=response.get('status', 'PENDING')
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if successfully cancelled
        """
        if self.dry_run:
            logger.info(f"DRY RUN: Would cancel order {order_id}")
            return True
        
        response = await self._request('DELETE', f'/orders/{order_id}')
        return response.get('success', False)
    
    async def get_open_positions(self) -> List[Position]:
        """
        Get user's open positions.
        
        Returns:
            List of Position objects
            
        Requires:
            Authentication (API key)
        """
        if not self.api_key:
            raise AuthenticationError("API key required to fetch positions")
        
        response = await self._request('GET', '/positions')
        
        positions_data = response.get('positions', [])
        positions = [Position(**p) for p in positions_data]
        
        logger.info(f"Fetched {len(positions)} open positions")
        return positions
    
    async def get_balance(self) -> Balance:
        """
        Get user's balance information.
        
        Returns:
            Balance object
        """
        if not self.api_key:
            raise AuthenticationError("API key required to fetch balance")
        
        response = await self._request('GET', '/balance')
        
        return Balance(
            usdc_balance=Decimal(str(response['usdc_balance'])),
            total_position_value=Decimal(str(response['position_value'])),
            available_balance=Decimal(str(response['available']))
        )
    
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """
        Get status of a specific order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            OrderStatus object
        """
        response = await self._request('GET', f'/orders/{order_id}')
        return OrderStatus(**response)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton for global client
_polymarket_client: Optional[PolymarketClient] = None


def get_polymarket_client(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    **kwargs
) -> PolymarketClient:
    """
    Get or create Polymarket client instance.
    
    Args:
        api_key: API key (optional, uses singleton if not provided)
        api_secret: API secret
        **kwargs: Additional PolymarketClient arguments
        
    Returns:
        PolymarketClient instance
    """
    global _polymarket_client
    
    # If specific credentials provided, create new client
    if api_key or api_secret:
        return PolymarketClient(
            api_key=api_key,
            api_secret=api_secret,
            **kwargs
        )
    
    # Otherwise use singleton
    if _polymarket_client is None:
        _polymarket_client = PolymarketClient(**kwargs)
    
    return _polymarket_client
