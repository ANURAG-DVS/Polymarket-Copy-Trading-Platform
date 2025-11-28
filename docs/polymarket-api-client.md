# Polymarket API Client - Usage Guide

## Overview

Comprehensive async Python client for Polymarket's CLOB (Central Limit Order Book) API with:
- ✅ API key authentication
- ✅ Automatic retry with exponential backoff
- ✅ Rate limit handling (100 req/min)
- ✅ Type-safe responses (Pydantic models)
- ✅ Mock/Testnet/Dry-run modes
- ✅ Comprehensive error handling

## Quick Start

### Installation

```python
# Already included in backend/requirements.txt
# httpx for async HTTP
# pydantic for response models
```

### Initialize Client

```python
from app.services.polymarket import PolymarketClient

# Production client
client = PolymarketClient(
    api_key="your_polymarket_api_key",
    api_secret="your_polymarket_api_secret"
)

# Testnet client (for testing)
testnet_client = PolymarketClient(
    api_key="test_key",
    testnet=True
)

# Mock mode (returns fake data for development)
mock_client = PolymarketClient(mock_mode=True)

# Dry-run mode (validates but doesn't execute trades)
dry_run_client = PolymarketClient(
    api_key="your_key",
    dry_run=True
)
```

## Market Data Methods

### 1. Get All Markets

```python
# Fetch active markets
markets = await client.get_markets(active_only=True, limit=100)

for market in markets:
    print(f"{market.question}")
    print(f"  Volume: ${market.volume}")
    print(f"  Liquidity: ${market.liquidity}")
    print(f"  Closes: {market.end_date}")
```

### 2. Get Specific Market

```python
market = await client.get_market_by_id("0x123...")

print(f"Question: {market.question}")
print(f"Active: {market.active}")
print(f"Resolved: {market.resolved}")
```

### 3. Get Current Prices

```python
prices = await client.get_market_prices("0x123...")

print(f"YES: ${prices.yes_price}")
print(f"NO: ${prices.no_price}")
print(f"Sum: {prices.yes_price + prices.no_price}")  # Should be ~1.0
```

### 4. Get Order Book

```python
# Get YES outcome order book
order_book = await client.get_order_book("0x123...", outcome="YES")

print(f"Best bid: ${order_book.bids[0]['price']}")
print(f"Best ask: ${order_book.asks[0]['price']}")
print(f"Spread: ${order_book.spread}")
print(f"Mid price: ${order_book.mid_price}")

# Analyze depth
total_bid_size = sum(level['size'] for level in order_book.bids)
print(f"Total bid liquidity: {total_bid_size} tokens")
```

## Trading Methods

### 1. Place Buy Order

```python
from decimal import Decimal

result = await client.place_buy_order(
    market_id="0x123...",
    outcome="YES",
    amount=Decimal("10.5"),  # Number of tokens to buy
    price=Decimal("0.55"),   # Maximum price willing to pay
    post_only=False          # Allow immediate fill
)

if result.success:
    print(f"Order placed: {result.order_id}")
    print(f"Transaction: {result.transaction_hash}")
    print(f"Filled: {result.filled_size} @ ${result.average_fill_price}")
    print(f"Fees: ${result.fees}")
    print(f"Status: {result.status}")
```

### 2. Place Sell Order

```python
result = await client.place_sell_order(
    market_id="0x123...",
    outcome="YES",
    amount=Decimal("5.0"),   # Number of tokens to sell
    price=Decimal("0.65"),   # Minimum price willing to accept
    post_only=True           # Don't fill immediately, post to book
)

print(f"Sell order: {result.order_id}")
```

### 3. Cancel Order

```python
success = await client.cancel_order("order_abc123")

if success:
    print("Order cancelled successfully")
```

### 4. Get Order Status

```python
status = await client.get_order_status("order_abc123")

print(f"Order {status.order_id}")
print(f"  Side: {status.side}")
print(f"  Status: {status.status}")
print(f"  Filled: {status.filled_size}/{status.size}")
print(f"  Remaining: {status.remaining_size}")
print(f"  Is Active: {status.is_active}")
```

## Position Management

### Get Open Positions

```python
positions = await client.get_open_positions()

for pos in positions:
    print(f"\n{pos.market_question}")
    print(f"  Outcome: {pos.outcome}")
    print(f"  Quantity: {pos.quantity} @ ${pos.average_price}")
    print(f"  Value: ${pos.current_value} (entry: ${pos.cost_basis})")
    print(f"  P&L: ${pos.unrealized_pnl} ({pos.unrealized_pnl_percent}%)")
```

### Get Balance

```python
balance = await client.get_balance()

print(f"USDC Balance: ${balance.usdc_balance}")
print(f"Position Value: ${balance.total_position_value}")
print(f"Available: ${balance.available_balance}")
```

## Error Handling

### Try-Catch Pattern

```python
from app.services.polymarket import (
    InsufficientFundsError,
    RateLimitError,
    MarketClosedError,
    InvalidOrderError,
    AuthenticationError
)

try:
    result = await client.place_buy_order(
        market_id="0x123...",
        outcome="YES",
        amount=Decimal("100"),
        price=Decimal("0.50")
    )
except AuthenticationError:
    print("Invalid API key")
except InsufficientFundsError as e:
    print(f"Not enough funds: {e}")
except MarketClosedError:
    print("Market is closed or inactive")
except InvalidOrderError as e:
    print(f"Invalid order params: {e}")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
    await asyncio.sleep(e.retry_after)
    # Retry...
```

### Check Error Category

```python
from app.services.polymarket import PolymarketAPIError

try:
    await client.get_markets()
except PolymarketAPIError as e:
    print(f"Error category: {e.category}")
    print(f"Status code: {e.status_code}")
    print(f"Response: {e.response_data}")
    
    if e.is_retryable():
        print("This error can be retried")
```

## Advanced Features

### Retry Configuration

```python
client = PolymarketClient(
    api_key="your_key",
    timeout=60  # Request timeout in seconds
)

# Retry configuration (built-in)
# - MAX_RETRIES = 3
# - RETRY_BACKOFF_BASE = 2 (exponential)
# - RETRY_BACKOFF_MAX = 60 seconds

# Automatic retry on:
# - Network errors
# - Rate limit errors
# - Server errors (5xx)
```

### Rate Limiting

```python
# Built-in rate limiting: 100 requests per 60 seconds
# Automatically enforced before each request

# If you hit the limit, RateLimitError is raised
try:
    for i in range(200):  # This will hit the limit
        await client.get_markets()
except RateLimitError as e:
    print(f"Hit rate limit, wait {e.retry_after}s")
```

### Dry-Run Mode (Testing)

```python
# Validate trades without executing
dry_run = PolymarketClient(
    api_key="your_key",
    dry_run=True
)

result = await dry_run.place_buy_order(
    market_id="0x123...",
    outcome="YES",
    amount=Decimal("1000"),  # Won't actually execute
    price=Decimal("0.99")
)

assert result.status == "DRY_RUN"
print("Order validation passed!")
```

### Mock Mode (Development)

```python
# Returns fake data for development
mock = PolymarketClient(mock_mode=True)

markets = await mock.get_markets()  # Returns []
order_book = await mock.get_order_book("any_id")  # Returns empty book

# No API calls are made
```

## Integration with Copy Trading

### Example: Copy a Trade

```python
async def copy_trade(
    original_tx_hash: str,
    trader_wallet: str,
    user_id: int,
    proportionality_factor: Decimal
):
    """
    Copy a trade from another trader.
    
    Args:
        original_tx_hash: Trader's transaction hash
        trader_wallet: Trader's wallet address
        user_id: Copying user's ID
        proportionality_factor: Size multiplier (e.g., 0.01 = 1%)
    """
    # 1. Fetch user's API credentials (from encrypted storage)
    from app.services.api_key_storage_service import get_api_key_storage_service
    
    storage_service = get_api_key_storage_service()
    credentials = await storage_service.retrieve_api_key(db, user_id)
    
    # 2. Create client
    client = PolymarketClient(
        api_key=credentials['api_key'],
        api_secret=credentials['api_secret']
    )
    
    # 3. Parse original trade (from blockchain event)
    # This would come from your blockchain monitoring service
    original_trade = {
        'market_id': '0x123...',
        'outcome': 'YES',
        'size': Decimal('100'),
        'price': Decimal('0.55')
    }
    
    # 4. Calculate copy size
    copy_size = original_trade['size'] * proportionality_factor
    
    # 5. Check spend limits
    from app.services.spend_limit_service import get_spend_limit_service
    
    spend_service = get_spend_limit_service()
    trade_value = copy_size * original_trade['price']
    
    await spend_service.check_spend_limit(
        db=db,
        user_id=user_id,
        key_id=credentials['key_id'],
        trade_amount_usd=trade_value
    )
    
    # 6. Place order
    try:
        result = await client.place_buy_order(
            market_id=original_trade['market_id'],
            outcome=original_trade['outcome'],
            amount=copy_size,
            price=original_trade['price']
        )
        
        # 7. Update spend tracking
        if result.success:
            await spend_service.update_spend_tracking(
                db=db,
                user_id=user_id,
                key_id=credentials['key_id'],
                trade_amount_usd=trade_value
            )
            
            # 8. Record trade in database
            # ... insert into trades table ...
            
            return result
            
    except InsufficientFundsError:
        logger.error(f"User {user_id} has insufficient funds")
        # Queue notification
        
    except RateLimitError as e:
        logger.warning(f"Rate limited, retrying in {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        # Add back to queue
        
    finally:
        await client.close()
```

## Cleanup

```python
# Always close the client when done
await client.close()

# Or use as async context manager
async with PolymarketClient(api_key="key") as client:
    markets = await client.get_markets()
    # Automatically closed after this block
```

## Error Codes Reference

| Error Class | Category | Retryable | Description |
|-------------|----------|-----------|-------------|
| `AuthenticationError` | `authentication` | ❌ | Invalid API key/credentials |
| `RateLimitError` | `rate_limit` | ✅ | Too many requests |
| `InsufficientFundsError` | `insufficient_funds` | ❌ | Not enough USDC balance |
| `MarketClosedError` | `market_closed` | ❌ | Market is inactive/closed |
| `InvalidOrderError` | `invalid_order` | ❌ | Bad order parameters |
| `NetworkError` | `network` | ✅ | Network/connection issue |
| `PolymarketAPIError` | `api_error` | ✅ | Generic API error |

## Performance Tips

1. **Reuse Client**: Create one client per user session, don't create/destroy for each request
2. **Batch Requests**: Fetch multiple markets at once instead of individual calls
3. **Cache Market Data**: Market metadata rarely changes, cache for 5-10 minutes
4. **Use Dry-Run**: Test order logic before live trading
5. **Monitor Rate Limits**: Track request count to avoid hitting 100/min limit

## Testing

```bash
# Run integration tests
cd backend
pytest tests/test_polymarket_client.py -v

# Run with coverage
pytest tests/test_polymarket_client.py --cov=app/services/polymarket
```

## References

- Polymarket API Docs: https://docs.polymarket.com
- CLOB API: https://clob.polymarket.com/docs
