"""
Integration Tests for Polymarket API Client

Tests with mocked HTTP responses.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import httpx

from app.services.polymarket.client import PolymarketClient
from app.services.polymarket.models import Market, MarketPrices, Position, TradeResult
from app.services.polymarket.errors import (
    RateLimitError, AuthenticationError, InvalidOrderError
)


@pytest.fixture
def mock_client():
    """Create client in mock mode"""
    return PolymarketClient(
        api_key="test_key",
        api_secret="test_secret",
        mock_mode=True
    )


@pytest.fixture
def testnet_client():
    """Create client for testnet"""
    return PolymarketClient(
        api_key="test_key",
        testnet=True
    )


@pytest.fixture
def dry_run_client():
    """Create client in dry-run mode"""
    return PolymarketClient(
        api_key="test_key",
        dry_run=True
    )


class TestPolymarketClient:
    """Test suite for PolymarketClient"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test client initialization"""
        client = PolymarketClient(
            api_key="key",
            api_secret="secret",
            testnet=True
        )
        
        assert client.api_key == "key"
        assert client.testnet is True
        assert client.base_url == PolymarketClient.TESTNET_URL
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_get_markets_mock_mode(self, mock_client):
        """Test get_markets in mock mode"""
        markets = await mock_client.get_markets()
        
        # Mock mode returns empty list
        assert isinstance(markets, list)
        assert len(markets) == 0
    
    @pytest.mark.asyncio
    async def test_get_markets_with_mocked_response(self):
        """Test get_markets with mocked HTTP response"""
        client = PolymarketClient(api_key="test")
        
        # Mock response data
        mock_response = {
            'markets': [
                {
                    'id': 'market_123',
                    'question': 'Will Bitcoin reach $100k in 2024?',
                    'description': 'Market description',
                    'end_date': '2024-12-31T23:59:59Z',
                    'tokens': ['0xabc', '0xdef'],
                    'outcome_prices': ['0.55', '0.45'],
                    'active': True,
                    'closed': False,
                    'volume': '10000.50',
                    'liquidity': '5000.25'
                }
            ]
        }
        
        # Mock the HTTP request
        with patch.object(client.client, 'request', new=AsyncMock(return_value=Mock(
            status_code=200,
            json=lambda: mock_response
        ))):
            markets = await client.get_markets()
            
            assert len(markets) == 1
            assert markets[0].id == 'market_123'
            assert markets[0].question == 'Will Bitcoin reach $100k in 2024?'
            assert markets[0].active is True
            assert markets[0].volume == Decimal('10000.50')
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_get_market_prices(self):
        """Test get_market_prices"""
        client = PolymarketClient(api_key="test")
        
        mock_response = {
            'yes_price': '0.62',
            'no_price': '0.38'
        }
        
        with patch.object(client.client, 'request', new=AsyncMock(return_value=Mock(
            status_code=200,
            json=lambda: mock_response
        ))):
            prices = await client.get_market_prices('market_123')
            
            assert prices.market_id == 'market_123'
            assert prices.yes_price == Decimal('0.62')
            assert prices.no_price == Decimal('0.38')
            assert prices.yes_price + prices.no_price == Decimal('1.00')
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_place_buy_order_dry_run(self, dry_run_client):
        """Test placing buy order in dry-run mode"""
        result = await dry_run_client.place_buy_order(
            market_id='market_123',
            outcome='YES',
            amount=Decimal('10'),
            price=Decimal('0.55')
        )
        
        assert result.success is True
        assert result.status == 'DRY_RUN'
        assert result.side == 'BUY'
        assert result.size == Decimal('10')
        assert result.price == Decimal('0.55')
    
    @pytest.mark.asyncio
    async def test_place_buy_order_with_response(self):
        """Test placing buy order with mocked response"""
        client = PolymarketClient(api_key="test")
        
        mock_response = {
            'order_id': 'order_456',
            'tx_hash': '0xabcdef',
            'filled': '5.0',
            'avg_price': '0.56',
            'fees': '0.02',
            'status': 'PARTIALLY_FILLED'
        }
        
        with patch.object(client.client, 'request', new=AsyncMock(return_value=Mock(
            status_code=200,
            json=lambda: mock_response
        ))):
            result = await client.place_buy_order(
                market_id='market_123',
                outcome='YES',
                amount=Decimal('10'),
                price=Decimal('0.55')
            )
            
            assert result.success is True
            assert result.order_id == 'order_456'
            assert result.transaction_hash == '0xabcdef'
            assert result.filled_size == Decimal('5.0')
            assert result.average_fill_price == Decimal('0.56')
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_invalid_order_price(self):
        """Test that invalid price raises error"""
        client = PolymarketClient(api_key="test")
        
        with pytest.raises(InvalidOrderError, match="Price must be between 0 and 1"):
            await client.place_buy_order(
                market_id='market_123',
                outcome='YES',
                amount=Decimal('10'),
                price=Decimal('1.5')  # Invalid: > 1
            )
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting enforcement"""
        client = PolymarketClient(api_key="test")
        
        # Simulate hitting rate limit
        client._request_timestamps = [1.0] * client.RATE_LIMIT_REQUESTS
        
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            await client._check_rate_limit()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """Test authentication error handling"""
        client = PolymarketClient(api_key="test")
        
        mock_response = {
            'error': 'Invalid API key'
        }
        
        with patch.object(client.client, 'request', new=AsyncMock(return_value=Mock(
            status_code=401,
            json=lambda: mock_response
        ))):
            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await client.get_markets()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        """Test retry logic on network error"""
        client = PolymarketClient(api_key="test")
        
        # First call fails, second succeeds
        call_count = 0
        
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.NetworkError("Connection failed")
            return Mock(status_code=200, json=lambda: {'markets': []})
        
        with patch.object(client.client, 'request', side_effect=mock_request):
            markets = await client.get_markets()
            
            # Should have retried once
            assert call_count == 2
            assert isinstance(markets, list)
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_get_open_positions(self):
        """Test fetching open positions"""
        client = PolymarketClient(api_key="test")
        
        mock_response = {
            'positions': [
                {
                    'market_id': 'market_123',
                    'market_question': 'Test question?',
                    'outcome': 'YES',
                    'quantity': '10.5',
                    'average_price': '0.55',
                    'current_price': '0.62',
                    'cost_basis': '577.50',
                    'current_value': '651.00'
                }
            ]
        }
        
        with patch.object(client.client, 'request', new=AsyncMock(return_value=Mock(
            status_code=200,
            json=lambda: mock_response
        ))):
            positions = await client.get_open_positions()
            
            assert len(positions) == 1
            pos = positions[0]
            assert pos.market_id == 'market_123'
            assert pos.quantity == Decimal('10.5')
            # P&L should be calculated automatically
            assert pos.unrealized_pnl == Decimal('73.50')  # 651 - 577.5
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, dry_run_client):
        """Test canceling an order"""
        result = await dry_run_client.cancel_order('order_123')
        
        # Dry run should return True
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_order_book(self):
        """Test fetching order book"""
        client = PolymarketClient(api_key="test")
        
        mock_response = {
            'bids': [
                {'price': '0.62', 'size': '100'},
                {'price': '0.61', 'size': '50'}
            ],
            'asks': [
                {'price': '0.63', 'size': '75'},
                {'price': '0.64', 'size': '25'}
            ]
        }
        
        with patch.object(client.client, 'request', new=AsyncMock(return_value=Mock(
            status_code=200,
            json=lambda: mock_response
        ))):
            order_book = await client.get_order_book('market_123', 'YES')
            
            assert len(order_book.bids) == 2
            assert len(order_book.asks) == 2
            assert order_book.bids[0]['price'] == Decimal('0.62')
            assert order_book.spread == Decimal('0.01')  # 0.63 - 0.62
            assert order_book.mid_price == Decimal('0.625')  # (0.62 + 0.63) / 2
        
        await client.close()


@pytest.mark.asyncio
class TestPolymarketClientEdgeCases:
    """Test edge cases and error conditions"""
    
    async def test_missing_api_key_for_authenticated_endpoint(self):
        """Test that authenticated endpoints require API key"""
        client = PolymarketClient()  # No API key
        
        with pytest.raises(AuthenticationError, match="API key required"):
            await client.get_open_positions()
        
        await client.close()
    
    async def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        client = PolymarketClient(api_key="test")
        
        # Test backoff timing
        backoff_1 = min(client.RETRY_BACKOFF_BASE ** 1, client.RETRY_BACKOFF_MAX)
        backoff_2 = min(client.RETRY_BACKOFF_BASE ** 2, client.RETRY_BACKOFF_MAX)
        backoff_3 = min(client.RETRY_BACKOFF_BASE ** 3, client.RETRY_BACKOFF_MAX)
        
        assert backoff_1 == 2  # 2^1
        assert backoff_2 == 4  # 2^2
        assert backoff_3 == 8  # 2^3
        
        # Test max cap
        backoff_high = min(client.RETRY_BACKOFF_BASE ** 10, client.RETRY_BACKOFF_MAX)
        assert backoff_high == client.RETRY_BACKOFF_MAX  # Should be capped
        
        await client.close()
    
    async def test_testnet_url_selection(self):
        """Test that testnet flag selects correct URL"""
        mainnet_client = PolymarketClient(testnet=False)
        testnet_client = PolymarketClient(testnet=True)
        
        assert mainnet_client.base_url == PolymarketClient.BASE_URL
        assert testnet_client.base_url == PolymarketClient.TESTNET_URL
        
        await mainnet_client.close()
        await testnet_client.close()
