# Market Data Caching - Usage Guide

## Overview

Redis-backed caching layer for Polymarket market data with:
- ✅ Automatic cache warming on startup
- ✅ 1-minute auto-refresh
- ✅ Graceful degradation on cache failure
- ✅ Cache hit/miss metrics
- ✅ Price pub/sub for real-time updates

## Quick Start

### 1. Initialize Cache

```python
from app.services.cache import get_market_cache_service

# Get cache service
cache = get_market_cache_service()
await cache.connect()

# Warm cache on startup
await cache.warm_cache()

# Start auto-refresh (every 1 minute)
await cache.start_auto_refresh()
```

### 2. Access Cached Data

```python
# Get single market
market = await cache.get_market("0x123...")
if market:
    print(f"{market.name}: YES ${market.yes_price}")

# Get all markets
markets = await cache.get_all_markets()
print(f"Found {len(markets)} markets")

# Get current prices (10s TTL)
prices = await cache.get_market_price("0x123...")
print(f"YES: ${prices['yes_price']}, NO: ${prices['no_price']}")

# Get trending markets
trending = await cache.get_trending_markets(limit=10)
```

## API Endpoints

### Get All Markets

```bash
GET /api/v1/markets?limit=50
```

Response:
```json
[
  {
    "market_id": "0x123...",
    "name": "Bitcoin to $100k by 2024?",
    "question": "Will Bitcoin reach $100,000 by end of 2024?",
    "end_date": "2024-12-31T23:59:59",
    "yes_price": 0.65,
    "no_price": 0.35,
    "volume_24h": 125000.50,
    "liquidity": 50000.00,
    "is_active": true,
    "last_updated": "2024-01-15T10:30:00"
  }
]
```

### Get Market Details

```bash
GET /api/v1/markets/0x123...
```

### Get Current Price

```bash
GET /api/v1/markets/0x123.../price
```

Response:
```json
{
  "market_id": "0x123...",
  "yes_price": 0.65,
  "no_price": 0.35
}
```

### Get Trending Markets

```bash
GET /api/v1/markets/trending?limit=10
```

### Get Cache Metrics

```bash
GET /api/v1/markets/metrics/cache
```

Response:
```json
{
  "cache_hits": 1542,
  "cache_misses": 89,
  "cache_errors": 2,
  "hit_rate": 94.54,
  "total_requests": 1631
}
```

## Cache Configuration

### TTL Settings

```python
# In market_cache.py
MARKET_TTL = 60  # 1 minute for markets
LIST_TTL = 60    # 1 minute for market list
PRICE_TTL = 10   # 10 seconds for prices
```

### Adjust Refresh Interval

```python
# In _auto_refresh_loop
await asyncio.sleep(60)  # Change to desired interval
```

## Cache Warming

### On Service Startup

```python
# In app/main.py
@app.on_event("startup")
async def startup():
    from app.services.cache import get_market_cache_service
    
    cache = get_market_cache_service()
    await cache.connect()
    await cache.warm_cache()
    await cache.start_auto_refresh()
```

### Manual Refresh

```python
# Force refresh all markets
await cache.warm_cache()
```

## Cache Invalidation

### Invalidate Single Market

```python
# When market closes or needs refresh
await cache.invalidate_market("0x123...")
```

Response (API):
```bash
POST /api/v1/markets/0x123.../invalidate
```

### Invalidate on Market Closure

```python
# In your market monitoring service
if market.end_date < datetime.utcnow():
    await cache.invalidate_market(market.market_id)
```

## Real-Time Price Updates

### Pub/Sub Pattern

Prices are published to Redis pub/sub channel: `market:prices`

```python
import redis.asyncio as redis

# Subscribe to price updates
async def subscribe_to_prices():
    r = await redis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    
    await pubsub.subscribe('market:prices')
    
    async for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            print(f"Price update: {data['market_id']} - ${data['yes_price']}")
```

## Graceful Degradation

Cache automatically falls back to API on failures:

```python
# If Redis unavailable, fetches from Polymarket API
market = await cache.get_market("0x123...")  # Still works!
```

## Performance

### Expected Performance

| Operation | Cached | Uncached |
|-----------|--------|----------|
| Get market | ~2ms | ~150ms |
| Get all markets | ~10ms | ~500ms |
| Get price | ~1ms | ~100ms |
| **Speedup** | **~75x** | **baseline** |

### Cache Hit Rate

Target: **>95%** hit rate

Monitor via metrics endpoint:
```bash
curl http://localhost:8000/api/v1/markets/metrics/cache
```

## Monitoring

### Metrics

Track via Prometheus:

```python
from prometheus_client import Counter, Histogram

cache_hits = Counter('market_cache_hits_total', 'Cache hits')
cache_misses = Counter('market_cache_misses_total', 'Cache misses')
cache_latency = Histogram('market_cache_latency_seconds', 'Cache latency')
```

### Health Check

```python
@app.get("/health/cache")
async def cache_health():
    cache = get_market_cache_service()
    metrics = cache.get_metrics()
    
    return {
        "healthy": metrics['cache_errors'] < 10,
        "hit_rate": metrics['hit_rate'],
        "total_requests": metrics['total_requests']
    }
```

## Troubleshooting

### Low Hit Rate (<90%)

**Causes:**
- Cache not warmed on startup
- TTL too short
- High invalidation rate

**Solutions:**
```python
# Increase TTL
MARKET_TTL = 120  # 2 minutes

# Verify auto-refresh is running
cache._refresh_task  # Should not be None
```

### Cache Misses on Startup

**Solution**: Warm cache in startup event
```python
@app.on_event("startup")
async def startup():
    cache = get_market_cache_service()
    await cache.warm_cache()
```

### Redis Connection Errors

**Solution**: Falls back to API automatically
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Check connection
redis-cli -u $REDIS_URL ping
```

## Best Practices

1. **Always warm cache on startup**
2. **Use shorter TTL for prices (10s)**
3. **Monitor cache hit rate (target >95%)**
4. **Invalidate on market closure**
5. **Enable auto-refresh for active service**

## Example: Full Integration

```python
# app/main.py
from fastapi import FastAPI
from app.services.cache import get_market_cache_service
from app.api.v1.endpoints import markets

app = FastAPI()

@app.on_event("startup")
async def startup():
    # Initialize cache
    cache = get_market_cache_service()
    await cache.connect()
    await cache.warm_cache()
    await cache.start_auto_refresh()
    
    print("Market cache initialized and warmed")

@app.on_event("shutdown")
async def shutdown():
    # Cleanup
    cache = get_market_cache_service()
    await cache.close()

# Include routes
app.include_router(markets.router, prefix="/api/v1")
```

## Testing

```python
import pytest
from app.services.cache import get_market_cache_service

@pytest.mark.asyncio
async def test_cache_market():
    cache = get_market_cache_service()
    await cache.connect()
    
    # Test cache miss (API call)
    market = await cache.get_market("0x123...", use_cache=False)
    assert market is not None
    
    # Test cache hit
    cached_market = await cache.get_market("0x123...", use_cache=True)
    assert cached_market.market_id == market.market_id
```

## Next Steps

1. **Initialize on Startup**: Add cache warming to `main.py`
2. **Monitor Metrics**: Track hit rate via `/markets/metrics/cache`
3. **Tune TTL**: Adjust based on data freshness needs
4. **Enable Auto-Refresh**: Keep cache current automatically
5. **Add Alerts**: Notify on low hit rate or high errors
