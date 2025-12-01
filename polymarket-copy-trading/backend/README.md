# Polymarket Copy Trading - Backend API

FastAPI backend for Polymarket copy trading platform with automated trader data synchronization from The Graph Protocol.

## Features

- 🚀 **Trader Data Pipeline** - Automated fetching from The Graph Protocol
- 📊 **Leaderboard System** - Real-time trader rankings by performance
- 💾 **Redis Caching** - High-performance data caching
- ⚡ **Background Tasks** - Celery-based periodic data updates
- 🔐 **Authentication** - JWT-based user authentication
- 📈 **Analytics** - Trader statistics and performance metrics
- 🎯 **Copy Trading** - Automated trade replication
- 💳 **Stripe Integration** - Subscription payments

## Tech Stack

- **FastAPI** 0.109.0 - Modern async web framework
- **PostgreSQL** 15 + TimescaleDB - Time-series data storage
- **Redis** 5.0 - Caching and message broker
- **Celery** 5.3 - Distributed task queue
- **SQLAlchemy** 2.0 - Async ORM
- **The Graph** - Blockchain data indexing

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 5.0+
- Docker (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/ANURAG-DVS/Polymarket-Copy-Trading-Platform.git
cd polymarket-copy-trading/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Run migrations
alembic upgrade head
```

### Running Services

**Development Mode:**

```bash
# Terminal 1 - Redis
redis-server

# Terminal 2 - PostgreSQL (Docker)
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=polymarket_copy_trading \
  postgres:15-alpine

# Terminal 3 - Celery Worker
celery -A app.core.celery_app worker --loglevel=info

# Terminal 4 - Celery Beat (Scheduler)
celery -A app.core.celery_app beat --loglevel=info

# Terminal 5 - Celery Flower (Monitoring)
celery -A app.core.celery_app flower --port=5555

# Terminal 6 - FastAPI
uvicorn app.main:app --reload --port 8000
```

**Production Mode:**

```bash
# Use supervisor or systemd for process management
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Trader Data System

### Architecture

```
The Graph Protocol → GraphClient → TraderDataFetcher → PostgreSQL
                                         ↓                ↓
                                    Celery Tasks    Redis Cache
                                         ↓
                                    FastAPI APIs
```

### Database Schema

**traders_v2:**
- `wallet_address` (PK) - Ethereum address
- `total_pnl` - Lifetime profit/loss
- `win_rate` - Win percentage
- `total_trades` - Total trade count
- `last_trade_at` - Last activity timestamp

**trader_stats** (TimescaleDB hypertable):
- `wallet_address` + `date` (composite PK)
- `daily_pnl` - Daily profit/loss
- `daily_volume` - Daily trading volume
- `trades_count`, `win_count`, `loss_count`

**trader_markets:**
- Position/trade data
- Market participation
- P&L per position

### Background Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| `fetch_top_traders` | Every 5 min | Fetch top 100 traders |
| `calculate_leaderboard` | Every 1 min | Recalculate rankings |
| `sync_trader_positions` | Every 10 min | Update position data |

### API Endpoints

#### Public Endpoints

```bash
# Get leaderboard
GET /api/v1/traders/leaderboard
  ?timeframe=7d
  &limit=100
  &min_trades=10
  &min_winrate=50

# Get trader details
GET /api/v1/traders/{wallet_address}

# Get trader statistics (chart data)
GET /api/v1/traders/{wallet_address}/statistics
  ?start_date=2024-01-01
  &end_date=2024-01-31

# Get trader positions
GET /api/v1/traders/{wallet_address}/positions
  ?status=open
  &limit=50

# Search traders
GET /api/v1/traders/search?q=0x123
```

#### Admin Endpoints

```bash
# Manual trigger trader fetch
POST /api/v1/admin/trigger-trader-fetch
{
  "limit": 100,
  "timeframe_days": 7
}

# Update trader statistics
POST /api/v1/admin/trigger-stats-update
{
  "wallet_addresses": ["0x123...", "0xabc..."],
  "days": 30
}

# Force leaderboard recalculation
POST /api/v1/admin/trigger-leaderboard-calc

# Full system sync
POST /api/v1/admin/trigger-full-sync

# Check task status
GET /api/v1/admin/task-status/{task_id}

# Worker health
GET /api/v1/admin/worker-stats
```

#### Health Check Endpoints

```bash
# Basic health check
GET /health

# Detailed health check (all dependencies)
GET /health/detailed

# Trader data health check
GET /health/traders
```

### Manual Trader Data Fetch

**Using admin API:**
```bash
curl -X POST http://localhost:8000/api/v1/admin/trigger-trader-fetch \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "timeframe_days": 7}'
```

**Using seed script:**
```bash
# Seed initial data (500 traders)
python -m scripts.seed_traders --limit 500 --days 30

# Verify data only
python -m scripts.seed_traders --verify-only
```

### Leaderboard Calculation Logic

Traders are ranked by **7-day P&L** (primary) with **win rate** as tiebreaker:

1. Calculate sum of `daily_pnl` for last 7 days
2. Order by total P&L descending
3. Apply win rate tiebreaker
4. Filter by minimum requirements:
   - `total_trades >= 10`
   - `total_volume >= 100`

**SQL Query:**
```sql
SELECT 
    ts.wallet_address,
    SUM(ts.daily_pnl) as pnl_7d,
    SUM(ts.trades_count) as trades_7d
FROM trader_stats ts
WHERE ts.date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY ts.wallet_address
HAVING SUM(ts.trades_count) >= 10
ORDER BY pnl_7d DESC;
```

### Caching Strategy

**Cache Keys:**
```
leaderboard:7d:{params_hash}    # TTL: 60s
trader:{wallet_address}          # TTL: 300s
trader_stats:{wallet_address}    # TTL: 180s
```

**Cache Flow:**
1. Check Redis cache first
2. If miss, query database
3. Store result in cache
4. Return to client

**Cache Invalidation:**
- Automatic on TTL expiration
- Manual via admin endpoint
- On data updates (write-through)

**Hit Rate Target:** >80%

## Configuration

### Environment Variables

See [`.env.example`](.env.example) for all variables.

**Required:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret
MASTER_ENCRYPTION_KEY=32-char-key
```

**The Graph Protocol:**
```bash
GRAPH_API_URL=https://api.thegraph.com/subgraphs/name/polymarket/matic-markets-5
GRAPH_API_KEY=  # Optional for higher rate limits
```

**Trader Configuration:**
```bash
TRADER_FETCH_INTERVAL=300        # 5 minutes
LEADERBOARD_CACHE_TTL=60         # 1 minute
TRADER_CACHE_TTL=300             # 5 minutes
MIN_TRADER_TRADES=10
MIN_TRADER_VOLUME=100.00
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/services/test_trader_fetcher.py -v

# Run specific test
pytest tests/services/test_trader_fetcher.py::test_fetch_and_store_new_traders
```

**Coverage Target:** >90%

## Monitoring

### Celery Flower Dashboard

View task execution, worker health, and statistics:
```bash
# Start Flower
celery -A app.core.celery_app flower --port=5555

# Access at http://localhost:5555
```

### Grafana Dashboard

Import the dashboard configuration:
```bash
# Located at monitoring/grafana_dashboard.json
```

**Panels:**
- Trader fetch success rate
- Leaderboard query performance
- Cache hit ratio
- Data freshness
- Task execution time

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check all dependencies
curl http://localhost:8000/health/detailed

# Check trader data freshness
curl http://localhost:8000/health/traders
```

## API Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Troubleshooting

### No traders in leaderboard

1. Check Celery worker is running
2. Check task execution in Flower
3. Verify database: `SELECT COUNT(*) FROM traders_v2;`
4. Check logs for errors

### Slow API responses

1. Check Redis connection: `redis-cli ping`
2. Verify cache hit rate in logs
3. Check database indexes
4. Monitor with Grafana

### Celery tasks not running

1. Check worker status: `celery -A app.core.celery_app inspect active`
2. Check Redis: `redis-cli ping`
3. Check beat scheduler: `celery -A app.core.celery_app inspect scheduled`

## Production Deployment

### Recommended Setup

- **Database:** PostgreSQL 15 + TimescaleDB extension
- **Cache:** Redis Cluster with persistence
- **Workers:** 4-8 Celery workers
- **API:** 4-8 Uvicorn workers behind Nginx
- **Monitoring:** Prometheus + Grafana + Sentry

### Performance Tuning

```python
# Database connection pooling
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Celery concurrency
CELERY_WORKER_CONCURRENCY=4

# Redis connection pool
REDIS_MAX_CONNECTIONS=10
```

## Project Structure

```
backend/
├── alembic/                    # Database migrations
│   └── versions/
├── app/
│   ├── api/                    # API routes
│   │   ├── deps.py            # Dependencies
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── traders.py  # Trader endpoints
│   │       │   ├── admin.py    # Admin endpoints
│   │       │   └── health.py   # Health checks
│   │       └── router.py
│   ├── core/                   # Core configuration
│   │   ├── config.py          # Settings
│   │   ├── celery_app.py      # Celery config
│   │   └── security.py
│   ├── models/                 # SQLAlchemy models
│   │   └── trader_v2.py       # Trader models
│   ├── schemas/                # Pydantic schemas
│   │   └── trader_v2.py
│   ├── services/               # Business logic
│   │   ├── graph_client.py    # Graph Protocol client
│   │   ├── graph_queries.py   # GraphQL queries
│   │   ├── trader_fetcher.py  # Data orchestration
│   │   └── cache_service.py   # Caching layer
│   ├── workers/                # Celery tasks
│   │   └── trader_tasks.py
│   └── main.py                 # FastAPI app
├── monitoring/
│   └── grafana_dashboard.json  # Grafana config
├── scripts/
│   └── seed_traders.py         # Data seeding
├── tests/
│   └── services/
│       └── test_trader_fetcher.py
├── .env.example                # Environment template
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see LICENSE file for details

## Support

- **Issues:** https://github.com/ANURAG-DVS/Polymarket-Copy-Trading-Platform/issues
- **Documentation:** See TRADER_INTEGRATION.md for detailed setup

---

**Built with ❤️ for the Polymarket community**
