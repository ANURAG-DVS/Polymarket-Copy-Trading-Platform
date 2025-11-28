# Trader API - Usage Guide

## Overview

Comprehensive REST API for trader information, leaderboard, and performance analytics with:
- ✅ Paginated leaderboard with multiple sorting options
- ✅ Complete trader profiles with stats
- ✅ Trade history with advanced filtering
- ✅ Performance chart data (daily buckets)
- ✅ ETag support for conditional requests
- ✅ Rate limiting (100 req/min per IP)
- ✅ Gzip compression

## API Endpoints

### 1. Get Leaderboard

```http
GET /api/v1/traders/leaderboard?timeframe=7d&sort_by=pnl&limit=100&offset=0
```

**Query Parameters:**
- `timeframe`: `7d`, `30d`, or `all` (default: `7d`)
- `sort_by`: `pnl`, `winrate`, `volume`, `sharpe` (default: `pnl`)
- `limit`: 1-500 (default: 100)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
{
  "timeframe": "7d",
  "sort_by": "pnl",
  "limit": 100,
  "offset": 0,
  "count": 100,
  "has_more": true,
  "traders": [
    {
      "rank": 1,
      "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
      "pnl_7d": 1250.50,
      "pnl_30d": 3420.75,
      "pnl_total": 12500.00,
      "win_rate_7d": 68.5,
      "win_rate_30d": 65.2,
      "total_trades": 42,
      "sharpe_ratio": 2.35
    }
  ]
}
```

**Pagination:**
```bash
# Page 1
GET /api/v1/traders/leaderboard?limit=50&offset=0

# Page 2
GET /api/v1/traders/leaderboard?limit=50&offset=50

# Page 3
GET /api/v1/traders/leaderboard?limit=50&offset=100
```

**Caching:**
- Response cached for 1 minute
- Returns `304 Not Modified` if ETag matches
- Include `If-None-Match` header with ETag

### 2. Get Trader Profile

```http
GET /api/v1/traders/{wallet_address}
```

**Response:**
```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
  "stats": {
    "rank": 15,
    "pnl_7d": 1250.50,
    "pnl_30d": 3420.75,
    "pnl_total": 12500.00,
    "win_rate_7d": 68.5,
    "win_rate_30d": 65.2,
    "win_rate_total": 62.8,
    "total_trades": 142,
    "total_trades_7d": 12,
    "total_trades_30d": 38,
    "sharpe_ratio": 2.35,
    "avg_trade_size": 125.50,
    "last_trade_at": "2024-01-15T10:30:00"
  },
  "name": null,
  "bio": null,
  "avatar_url": null,
  "followers": 0,
  "following": 0
}
```

**ETag Support:**
```bash
# First request
curl -i http://localhost:8000/api/v1/traders/0x123...
# Returns: ETag: "abc123456"

# Subsequent request
curl -H 'If-None-Match: "abc123456"' http://localhost:8000/api/v1/traders/0x123...
# Returns: 304 Not Modified (if unchanged)
```

### 3. Get Trade History

```http
GET /api/v1/traders/{wallet_address}/trades?limit=50&offset=0
```

**Query Parameters:**
- `limit`: 1-500 (default: 50)
- `offset`: Pagination offset
- `market_id`: Filter by market (optional)
- `outcome`: `YES` or `NO` (optional)
- `status`: `open` or `closed` (optional)
- `start_date`: ISO datetime (optional)
- `end_date`: ISO datetime (optional)

**Response:**
```json
{
  "wallet_address": "0x742d35Cc...",
  "total": 142,
  "limit": 50,
  "offset": 0,
  "has_more": true,
  "trades": [
    {
      "id": 12345,
      "tx_hash": "0xabc...",
      "market_id": "0x123...",
      "market_name": "Bitcoin to $100k by 2024?",
      "side": "BUY",
      "outcome": "YES",
      "quantity": 100.0,
      "entry_price": 0.65,
      "entry_value_usd": 650.00,
      "exit_price": 0.72,
      "exit_value_usd": 720.00,
      "realized_pnl_usd": 70.00,
      "realized_pnl_percent": 10.77,
      "status": "closed",
      "entry_timestamp": "2024-01-10T14:30:00",
      "exit_timestamp": "2024-01-12T16:45:00"
    }
  ]
}
```

**Filtering Examples:**
```bash
# Only closed trades
GET /api/v1/traders/0x123.../trades?status=closed

# Specific market
GET /api/v1/traders/0x123.../trades?market_id=0xabc...

# YES outcomes only
GET /api/v1/traders/0x123.../trades?outcome=YES

# Date range
GET /api/v1/traders/0x123.../trades?start_date=2024-01-01T00:00:00&end_date=2024-01-31T23:59:59

# Combined filters
GET /api/v1/traders/0x123.../trades?status=closed&outcome=YES&limit=20
```

### 4. Get Performance Chart Data

```http
GET /api/v1/traders/{wallet_address}/performance?timeframe=30d
```

**Query Parameters:**
- `timeframe`: `7d`, `30d`, `90d`, or `all` (default: `30d`)

**Response:**
```json
{
  "wallet_address": "0x742d35Cc...",
  "timeframe": "30d",
  "data_points": [
    {
      "date": "2024-01-01",
      "pnl": 125.50,
      "cumulative_pnl": 125.50,
      "trades_count": 3
    },
    {
      "date": "2024-01-02",
      "pnl": -45.20,
      "cumulative_pnl": 80.30,
      "trades_count": 2
    },
    {
      "date": "2024-01-03",
      "pnl": 220.00,
      "cumulative_pnl": 300.30,
      "trades_count": 5
    }
  ]
}
```

**Chart Integration (Chart.js):**
```javascript
// Fetch data
const response = await fetch('/api/v1/traders/0x123.../performance?timeframe=30d');
const data = await response.json();

// Chart.js config
const chartConfig = {
  type: 'line',
  data: {
    labels: data.data_points.map(d => d.date),
    datasets: [{
      label: 'Cumulative P&L',
      data: data.data_points.map(d => d.cumulative_pnl),
      borderColor: 'rgb(75, 192, 192)',
      tension: 0.1
    }]
  },
  options: {
    responsive: true,
    plugins: {
      title: {
        display: true,
        text: 'Trader Performance'
      }
    }
  }
};
```

**Chart Integration (Recharts):**
```jsx
import { LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';

function PerformanceChart({ walletAddress }) {
  const [data, setData] = useState([]);
  
  useEffect(() => {
    fetch(`/api/v1/traders/${walletAddress}/performance?timeframe=30d`)
      .then(res => res.json())
      .then(json => setData(json.data_points));
  }, [walletAddress]);
  
  return (
    <LineChart width={600} height={300} data={data}>
      <XAxis dataKey="date" />
      <YAxis />
      <Tooltip />
      <Line type="monotone" dataKey="cumulative_pnl" stroke="#8884d8" />
    </LineChart>
  );
}
```

## Rate Limiting

**Limits:**
- 100 requests per minute per IP
- Sliding window algorithm

**Headers:**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705320660
```

**Error Response (429):**
```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

```http
Retry-After: 60
```

## Response Caching

### ETag Support

All endpoints support ETags for conditional requests:

```bash
# Initial request
curl -i http://localhost:8000/api/v1/traders/leaderboard
# Response includes: ETag: "abc123"

# Subsequent request with ETag
curl -H 'If-None-Match: "abc123"' http://localhost:8000/api/v1/traders/leaderboard
# Returns 304 Not Modified if unchanged
```

**Benefits:**
- Reduced bandwidth usage
- Faster response times
- Lower server load

### Cache-Control Headers

```http
Cache-Control: public, max-age=60
```

Responses cached for 1 minute by browsers and CDNs.

## Gzip Compression

Enable gzip compression in FastAPI:

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**Benefits:**
- ~70-80% size reduction for JSON responses
- Faster transfer times
- Lower bandwidth costs

## Error Handling

### 404 Not Found

```json
{
  "detail": "Market not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["query", "timeframe"],
      "msg": "string does not match regex \"^(7d|30d|all)$\"",
      "type": "value_error.str.regex"
    }
  ]
}
```

### 429 Rate Limit

```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

## Examples

### Python (requests)

```python
import requests

# Get leaderboard
response = requests.get(
    'http://localhost:8000/api/v1/traders/leaderboard',
    params={'timeframe': '7d', 'limit': 50}
)
leaderboard = response.json()

# Get trader profile
profile = requests.get(
    f'http://localhost:8000/api/v1/traders/0x742d35Cc...'
).json()

# Get trades with filtering
trades = requests.get(
    f'http://localhost:8000/api/v1/traders/0x742d35Cc.../trades',
    params={'status': 'closed', 'limit': 20}
).json()

# Get performance data
performance = requests.get(
    f'http://localhost:8000/api/v1/traders/0x742d35Cc.../performance',
    params={'timeframe': '30d'}
).json()
```

### JavaScript (fetch)

```javascript
// Get leaderboard
const leaderboard = await fetch(
  '/api/v1/traders/leaderboard?timeframe=7d&limit=50'
).then(res => res.json());

// Get trader profile with ETag
const etag = localStorage.getItem('trader_etag');
const response = await fetch('/api/v1/traders/0x742d35Cc...', {
  headers: etag ? { 'If-None-Match': etag } : {}
});

if (response.status === 304) {
  // Use cached data
  profile = JSON.parse(localStorage.getItem('trader_profile'));
} else {
  profile = await response.json();
  localStorage.setItem('trader_profile', JSON.stringify(profile));
  localStorage.setItem('trader_etag', response.headers.get('ETag'));
}

// Get performance data
const performance = await fetch(
  '/api/v1/traders/0x742d35Cc.../performance?timeframe=30d'
).then(res => res.json());
```

## Testing

### cURL Examples

```bash
# Leaderboard
curl "http://localhost:8000/api/v1/traders/leaderboard?timeframe=7d&limit=10"

# Trader profile
curl "http://localhost:8000/api/v1/traders/0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"

# Trade history
curl "http://localhost:8000/api/v1/traders/0x742d35Cc.../trades?status=closed&limit=20"

# Performance
curl "http://localhost:8000/api/v1/traders/0x742d35Cc.../performance?timeframe=30d"

# With ETag
curl -H 'If-None-Match: "abc123"' "http://localhost:8000/api/v1/traders/leaderboard"
```

## OpenAPI Documentation

Access interactive API docs at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Best Practices

1. **Use ETag headers** to reduce bandwidth
2. **Implement pagination** for large result sets
3. **Cache responses** on client side (1 min TTL)
4. **Handle 304 responses** to use cached data
5. **Respect rate limits** (check headers)
6. **Filter trades** to reduce response size
7. **Use appropriate timeframes** for charts

## Performance

| Endpoint | Avg Response Time | Max Response Size |
|----------|------------------|-------------------|
| Leaderboard (100) | 50-150ms | ~50KB |
| Trader Profile | 30-80ms | ~2KB |
| Trade History (50) | 100-200ms | ~30KB |
| Performance (30d) | 80-150ms | ~10KB |

With caching (ETag 304): **~5ms**

## Next Steps

1. **Integrate with Frontend**: Use endpoints in React/Next.js
2. **Add Monitoring**: Track API usage and performance
3. **Implement Search**: Add trader search by address/name
4. **Add Follows**: Endpoints for following/unfollowing traders
5. **Real-time Updates**: WebSocket for live leaderboard updates
