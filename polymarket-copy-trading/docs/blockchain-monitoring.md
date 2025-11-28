# Polygon Blockchain Monitoring - Setup Guide

## Overview

Reliable blockchain monitoring system for tracking Polymarket trades on Polygon network with:
- ✅ Multi-provider RPC with automatic failover
- ✅ WebSocket & polling support
- ✅ Health monitoring & latency tracking
- ✅ Event filtering & parsing
- ✅ Automatic recovery from connection failures

## Architecture

```
┌──────────────────────────────────────────────────┐
│         Block Monitor Service                     │
│  • Subscribe to new blocks                        │
│  • Filter Polymarket transactions                │
│  • Parse trade events                            │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│      Web3 Provider Service                       │
│  • Connection pool management                     │
│  • Automatic failover                            │
│  • Health monitoring                             │
│  • Request caching                               │
└───┬──────────┬──────────┬──────────┬─────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Alchemy │ │WebSocket│ │Fallback│ │Fallback│
│  HTTP  │ │  (WSS) │ │   #1   │ │   #2   │
└────────┘ └────────┘ └────────┘ └────────┘
```

## Quick Setup

### 1. Get RPC Endpoints

#### Option A: Alchemy (Recommended for Development)

1. Visit https://dashboard.alchemy.com/
2. Create free account
3. Click "Create App"
4. Select:
   - Chain: **Polygon PoS**
   - Network: **Mainnet**
5. Copy your endpoints:
   - HTTP: `https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY`
   - WebSocket: `wss://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY`

**Free Tier**: 300M compute units/month (~100k requests)

#### Option B: QuickNode (Recommended for Production)

1. Visit https://www.quicknode.com/
2. Create account
3. Click "Create Endpoint"
4. Select: **Polygon Mainnet**
5. Choose plan (starting at $9/month)
6. Copy HTTP & WSS endpoints

**Benefits**: Fastest response times, 99.9% uptime SLA

#### Option C: Infura

1. Visit https://infura.io/
2. Create account & project
3. Select **Polygon POS** network
4. Copy endpoints from dashboard

### 2. Configure Environment

Edit `.env`:

```bash
# Primary RPC (Alchemy)
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# WebSocket for real-time monitoring
POLYGON_RPC_WSS=wss://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# Fallback RPCs (public endpoints for redundancy)
POLYGON_RPC_FALLBACKS=https://polygon-rpc.com,https://rpc-mainnet.matic.network

# Monitoring settings
BLOCKCHAIN_POLLING_INTERVAL=12
BLOCKCHAIN_ENABLE_WEBSOCKET=true
```

### 3. Install Dependencies

```bash
pip install web3==6.11.3
```

Already included in `requirements.txt`.

### 4. Test Connection

```python
from app.services.blockchain import get_web3_provider_service

# Test connection
provider = get_web3_provider_service()
w3 = await provider.connect()

# Get latest block
block_number = await w3.eth.block_number
print(f"Connected! Latest block: {block_number}")

# Check provider status
status = provider.get_status()
print(f"Current provider: {status['current_endpoint']}")
print(f"Latency: {status['endpoints'][0]['latency_ms']}ms")
```

## Usage Examples

### Monitor New Blocks

```python
from app.services.blockchain import get_block_monitor_service

# Create monitor
monitor = get_block_monitor_service()

# Register callback for new trades
async def on_new_trade(event):
    print(f"New trade detected!")
    print(f"  Trader: {event.trader_address}")
    print(f"  Market: {event.market_id}")
    print(f"  Side: {event.side}")
    print(f"  Size: {event.size} @ ${event.price}")
    
    # Insert into database, trigger copy trade, etc.

monitor.on_trade_event(on_new_trade)

# Start monitoring (from latest block)
await monitor.start()

# Or start from specific block
await monitor.start(from_block=50000000)
```

### Monitor Specific Contracts

```python
from app.services.blockchain import BlockMonitorConfig, POLYMARKET_CONTRACTS

# Monitor only CTF Exchange contract
config = BlockMonitorConfig(
    monitored_contracts={POLYMARKET_CONTRACTS['CTF_EXCHANGE']},
    use_websocket=True,
    polling_interval=10
)

monitor = BlockMonitorService(config)
await monitor.start()
```

### Get Provider Status

```python
provider = get_web3_provider_service()

# Health status
status = provider.get_status()

print(f"Current RPC: {status['current_endpoint']}")
print(f"\nAll Endpoints:")
for endpoint in status['endpoints']:
    print(f"  {endpoint['name']}: "
          f"{'✓' if endpoint['healthy'] else '✗'} "
          f"{endpoint['latency_ms']:.1f}ms "
          f"({endpoint['total_requests']} requests, "
          f"{endpoint['total_failures']} failures)")
```

### Manual Failover

```python
# Force reconnection (will try next healthy endpoint)
await provider.connect()
```

## Polymarket Contract Addresses

All deployed on **Polygon Mainnet**:

| Contract | Address | Purpose |
|----------|---------|---------|
| CTF Exchange | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | Main trading |
| CTF (Conditional Tokens) | `0x4D97DCd97eC945f40Cf65F87097ACe5EA0476045` | Token framework |
| Order Book | `0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40` | Order matching |
| Neg Risk CTF Exchange | `0xC5d563A36AE78145C45a50134d48A1215220f80a` | Neg risk markets |

Verify on PolygonScan: https://polygonscan.com/address/0x4bFb...

## Event Signatures

Key events to monitor:

```python
from app.services.blockchain.contracts import EVENT_SIGNATURES

# OrderFilled - when a trade executes
EVENT_SIGNATURES['OrderFilled']
# '0x52a2c9e52d3f2c8f7a75b3b0e0e3c1c2f7e3b8c5d8e2f3a4b5c6d7e8f9a0b1c2'

# PositionSplit - when outcome tokens are minted
EVENT_SIGNATURES['PositionSplit']

# Transfer - ERC20/ERC1155 transfers
EVENT_SIGNATURES['Transfer']
```

## Performance Optimization

### 1. Connection Pooling

The Web3 provider automatically manages connections. For high throughput:

```python
config = RPCProviderConfig(
    request_timeout=10,  # Faster timeout
    max_retries=2,       # Fewer retries
    cache_ttl=5          # Shorter cache (for frequently changing data)
)

provider = Web3ProviderService(config)
```

### 2. Batch Requests

Process multiple blocks in batches:

```python
config = BlockMonitorConfig(
    max_blocks_per_batch=50,  # Process 50 blocks at once
    log_batch_size=1000       # Fetch up to 1000 logs per request
)
```

### 3. Request Caching

Frequently accessed data is cached (10s TTL by default):

```python
# This will be cached
block = await provider.execute_with_retry(
    'eth.get_block',
    block_number,
    cache_key=f'block_{block_number}'
)

# Second call within 10s hits cache (no RPC request)
block_cached = await provider.execute_with_retry(
    'eth.get_block',
    block_number,
    cache_key=f'block_{block_number}'
)
```

## Troubleshooting

### Error: "Unable to connect to any RPC endpoint"

**Cause**: All RPC endpoints are failing

**Solution**:
1. Check API keys are correct
2. Verify network connectivity
3. Check Alchemy/Infura dashboard for rate limits
4. Try public fallback: `https://polygon-rpc.com`

### Error: "Rate limit exceeded"

**Cause**: Too many requests to RPC provider

**Solution**:
1. Upgrade Alchemy plan (free → Growth)
2. Add more fallback endpoints
3. Increase caching TTL
4. Reduce polling frequency

### Slow Response Times

**Cause**: High latency RPC endpoint

**Solution**:
1. Check endpoint latency: `provider.get_status()`
2. Switch to QuickNode (typically <50ms)
3. Use geographic RPC closer to your deployment
4. Enable WebSocket for lower latency

### Missing Trade Events

**Cause**: Block gaps or connection interruptions

**Solution**:
1. Enable recovery: `BLOCKCHAIN_RECOVERY_LOOKBACK=100`
2. Check monitor status: `monitor.get_status()`
3. Verify from_block is correct
4. Check logs for connection errors

## Monitoring in Production

### Health Checks

```python
# Add to FastAPI health endpoint
@app.get("/health/blockchain")
async def blockchain_health():
    provider = get_web3_provider_service()
    monitor = get_block_monitor_service()
    
    provider_status = provider.get_status()
    monitor_status = monitor.get_status()
    
    return {
        "provider": {
            "healthy": any(e['healthy'] for e in provider_status['endpoints']),
            "current_rpc": provider_status['current_endpoint'],
            "latency_ms": provider_status['endpoints'][0]['latency_ms']
        },
        "monitor": {
            "running": monitor_status['is_running'],
            "latest_block": monitor_status['latest_processed_block'],
            "total_trades": monitor_status['total_trades_detected'],
            "uptime_hours": monitor_status.get('uptime_seconds', 0) / 3600
        }
    }
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Gauge

# Add metrics
blocks_processed = Counter('blockchain_blocks_processed_total', 'Total blocks processed')
trades_detected = Counter('blockchain_trades_detected_total', 'Total trades detected')
rpc_latency = Gauge('blockchain_rpc_latency_ms', 'RPC latency in milliseconds')

# Update in callbacks
async def on_new_trade(event):
    trades_detected.inc()
    # ... process trade
```

### Alerting

Set up alerts for:
- ❌ All RPC endpoints unhealthy (critical)
- ❌ No blocks processed in 5 minutes (critical)
- ⚠️ RPC latency > 1000ms (warning)
- ⚠️ RPC failure rate > 10% (warning)

## Cost Estimation

### Alchemy Free Tier

- **300M compute units/month**
- `eth_getLogs`: ~100 CU per call
- `eth_blockNumber`: ~10 CU
- `eth_getBlock`: ~16 CU

Monitoring 1 trade/minute:
- ~4,320 trades/month
- ~500k CU/month for logs
- **Well within free tier** ✓

### Alchemy Growth ($49/month)

- **300M CU/month**
- Suitable for low-volume production

### QuickNode ($9-299/month)

- **Build Plan ($9/mo)**: 10M requests/month
- **Scale Plan ($49/mo)**: 100M requests/month
- **Enterprise**: Custom pricing

## Next Steps

1. **Test locally**: Run block monitor with testnet
2. **Deploy backend**: Start monitoring service with supervisor/systemd
3. **Implement trade copying**: Build worker that processes TradeEvent
4. **Add database persistence**: Store processed blocks for recovery
5. **Set up monitoring**: Add health checks and alerts

## Resources

- Polygon RPC Endpoints: https://wiki.polygon.technology/docs/develop/network-details/network/
- Polymarket Docs: https://docs.polymarket.com
- Web3.py Docs: https://web3py.readthedocs.io/
- PolygonScan: https://polygonscan.com/
