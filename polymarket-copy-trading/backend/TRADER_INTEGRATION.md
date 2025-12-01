# Trader Data Integration - Setup Guide

This document explains how the trader data layer is integrated with the FastAPI backend.

## Architecture Overview

```
┌─────────────────────┐
│  The Graph Protocol │  ← Data Source
│   (Polymarket Data) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  GraphClient        │  ← Async HTTP Client
│  (app/services)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ TraderDataFetcher   │  ← Orchestration
│  (app/services)     │
└──────────┬──────────┘
           │
           ├──────────┐
           │          │
           ▼          ▼
    ┌─────────┐  ┌─────────┐
    │ Celery  │  │  Redis  │
    │ Workers │  │  Cache  │
    └────┬────┘  └────┬────┘
         │            │
         └────────┬───┘
                  │
                  ▼
         ┌────────────────┐
         │   PostgreSQL   │
         │   - traders_v2 │
         │   - trader_stats│
         │   - trader_markets│
         └────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │   FastAPI      │
         │   REST APIs    │
         └────────────────┘
```

## Components Integrated

### 1. Main Application (`app/main.py`)

**Added:**
- ✅ Admin router for manual task triggering
- ✅ Startup event to queue initial trader fetch
- ✅ Shutdown event for cleanup

```python
@app.on_event("startup")
async def startup_event():
    # Trigger initial data fetch on app startup
    fetch_top_traders_task.delay(limit=100, timeframe_days=7)

@app.on_event("shutdown")
async def shutdown_event():
    # Close Redis connections gracefully
    await close_redis()
```

### 2. Configuration (`app/core/config.py`)

**Added Settings:**
```python
# The Graph Protocol
GRAPH_API_URL: str = "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets-5"
GRAPH_API_KEY: Optional[str] = None  # Optional for higher rate limits

# Trader Configuration
TRADER_FETCH_INTERVAL: int = 300     # Fetch every 5 minutes
LEADERBOARD_CACHE_TTL: int = 60      # Cache leaderboard for 1 minute
TRADER_CACHE_TTL: int = 300          # Cache trader details for 5 minutes
MIN_TRADER_TRADES: int = 10          # Minimum trades for leaderboard
MIN_TRADER_VOLUME: str = "100.00"    # Minimum volume
```

### 3. API Routers (`app/api/v1/router.py`)

**Already Included:**
- ✅ Traders router at `/api/v1/traders`

**Endpoints Available:**
- `GET /api/v1/traders/leaderboard` - Top traders with filters
- `GET /api/v1/traders/{wallet_address}` - Trader details
- `GET /api/v1/traders/{wallet_address}/statistics` - Time-series data
- `GET /api/v1/traders/{wallet_address}/positions` - Position history
- `GET /api/v1/traders/search` - Search traders

**Admin Endpoints:**
- `POST /api/v1/admin/trigger-trader-fetch` - Manual fetch
- `POST /api/v1/admin/trigger-stats-update` - Update stats
- `POST /api/v1/admin/trigger-leaderboard-calc` - Recalculate rankings
- `POST /api/v1/admin/trigger-full-sync` - Complete sync
- `GET /api/v1/admin/task-status/{task_id}` - Check task status
- `GET /api/v1/admin/worker-stats` - Worker health

## Setup Instructions

### 1. Environment Variables

Copy the example environment file:
```bash
cp backend/.env.example backend/.env
```

**Required variables:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/polymarket_copy_trading

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# The Graph Protocol (optional key for higher limits)
GRAPH_API_KEY=your-graph-api-key
```

### 2. Database Migration

Run the migration to create trader tables:
```bash
cd backend
alembic upgrade head
```

This creates:
- `traders_v2` - Main trader data
- `trader_stats` - Daily statistics (TimescaleDB hypertable)
- `trader_markets` - Position/trade data

### 3. Start Required Services

**Redis:**
```bash
redis-server
```

**PostgreSQL:**
```bash
# Using Docker
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=polymarket_copy_trading \
  postgres:15-alpine
```

**Celery Worker:**
```bash
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

**Celery Beat (Scheduler):**
```bash
cd backend
celery -A app.core.celery_app beat --loglevel=info
```

**Celery Flower (Monitoring):**
```bash
cd backend
celery -A app.core.celery_app flower --port=5555
```
Visit: http://localhost:5555

### 4. Start FastAPI Application

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## Automated Background Tasks

### Task Schedule

Configured in `app/core/celery_app.py`:

| Task | Schedule | Purpose |
|------|----------|---------|
| `fetch_top_traders` | Every 5 minutes | Fetch and store top 100 traders |
| `calculate_leaderboard` | Every 1 minute | Recalculate rankings and cache |
| `sync_trader_positions` | Every 10 minutes | Sync position data for top 50 |

### Manual Triggers

Use admin endpoints to manually trigger tasks:

```bash
# Trigger trader fetch
curl -X POST http://localhost:8000/api/v1/admin/trigger-trader-fetch

# Full sync (all tasks)
curl -X POST http://localhost:8000/api/v1/admin/trigger-full-sync

# Check task status
curl http://localhost:8000/api/v1/admin/task-status/{task_id}
```

## API Usage Examples

### Get Leaderboard

```bash
curl "http://localhost:8000/api/v1/traders/leaderboard?limit=10&min_trades=20"
```

**Response:**
```json
{
  "traders": [
    {
      "rank": 1,
      "wallet_address": "0x123...",
      "total_pnl": 5000.50,
      "win_rate": 68.5,
      "total_trades": 150
    }
  ],
  "total": 95,
  "page": 1,
  "limit": 10,
  "total_pages": 10
}
```

### Get Trader Details

```bash
curl "http://localhost:8000/api/v1/traders/0x123..."
```

**Response:**
```json
{
  "trader": {
    "wallet_address": "0x123...",
    "total_pnl": 5000.50,
    "win_rate": 68.5
  },
  "metrics": {
    "pnl_7d": 450.25,
    "pnl_30d": 1850.00
  },
  "recent_positions": [...],
  "chart_data": [...]
}
```

## Monitoring

### Celery Flower Dashboard
- URL: http://localhost:5555
- Monitor task execution, worker health, and task history

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Logs

```bash
# Application logs
tail -f logs/app.log

# Celery worker logs
celery -A app.core.celery_app worker --loglevel=debug
```

## Caching Strategy

### Redis Keys

```
leaderboard:7d:{params_hash}     # TTL: 60s
trader:{wallet_address}           # TTL: 300s
trader_stats:{wallet_address}     # TTL: 180s
```

### Cache Warming

On application startup:
1. Initial trader fetch queued
2. Leaderboard calculated
3. Top 50 trader positions synced

### Cache Invalidation

Cache is automatically invalidated:
- On data updates (write-through)
- On TTL expiration
- Manual via admin endpoint

## Troubleshooting

### No traders appearing on leaderboard

**Check:**
1. Celery worker is running
2. Initial data fetch completed: Check Flower dashboard
3. Database has data: `SELECT COUNT(*) FROM traders_v2;`
4. Graph API is accessible: Check worker logs

### Slow API responses

**Solutions:**
1. Increase cache TTL in config
2. Check Redis connection
3. Add database indexes
4. Scale Celery workers

### Celery tasks not executing

**Check:**
1. Celery worker running: `celery -A app.core.celery_app inspect active`
2. Redis connection: `redis-cli ping`
3. Task queue: `celery -A app.core.celery_app inspect reserved`

## Production Deployment

### Recommended Setup

1. **Database**: PostgreSQL + TimescaleDB extension
2. **Cache**: Redis cluster with persistence
3. **Workers**: Multiple Celery workers for redundancy
4. **Monitoring**: Prometheus + Grafana
5. **CDN**: Cache API responses at edge

### Environment Variables

Set in production:
```bash
NODE_ENV=production
GRAPH_API_KEY=<your-production-key>  # Higher rate limits
MIN_TRADER_TRADES=50  # Stricter filtering
```

## Next Steps

1. ✅ API integration complete
2. ✅ Background tasks configured
3. ✅ Caching implemented
4. 🔄 Frontend integration (next phase)
5. 🔄 WebSocket real-time updates
6. 🔄 Performance monitoring

## Support

For issues:
1. Check logs in `/logs` directory
2. Verify services are running
3. Check Celery Flower dashboard
4. Review API docs at `/docs`
