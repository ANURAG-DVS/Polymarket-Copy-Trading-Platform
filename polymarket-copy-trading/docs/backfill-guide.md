# Historical Data Backfill - Setup & Usage Guide

## Overview

One-time script to seed the trader leaderboard with historical Polymarket data from the last 90 days.

**Features:**
- ✅ Fetches blockchain events in paginated chunks
- ✅ Progress tracking with resume capability
- ✅ Batch processing (1000 transactions at a time)
- ✅ Data validation and quality reporting
- ✅ CLI interface with progress bars
- ✅ Estimated completion time

## Installation

### 1. Install Dependencies

```bash
pip install tqdm  # Progress bars
```

Already included in `requirements.txt`.

### 2. Ensure Database is Ready

```bash
# Run migrations
cd backend
alembic upgrade head

# Verify traders table exists
psql $DATABASE_URL -c "\d traders"
```

### 3. Set Environment Variables

Ensure `.env` has:
```bash
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
DATABASE_URL=postgresql+asyncpg://...
```

## Usage

### Basic Backfill (Last 90 Days)

```bash
cd backend
python scripts/backfill_leaderboard.py
```

### Custom Time Range

```bash
# Last 30 days
python scripts/backfill_leaderboard.py --days 30

# Last 180 days (6 months)
python scripts/backfill_leaderboard.py --days 180
```

### Adjust Batch Size

```bash
# Smaller batches (more checkpoints, slower)
python scripts/backfill_leaderboard.py --batch-size 500

# Larger batches (fewer checkpoints, faster)
python scripts/backfill_leaderboard.py --batch-size 2000
```

### Resume After Interruption

```bash
# If script fails or is interrupted
python scripts/backfill_leaderboard.py --resume
```

### Verbose Logging

```bash
python scripts/backfill_leaderboard.py --verbose
```

## Progress Tracking

### Checkpoint File

Progress saved to `backfill_checkpoint.json`:

```json
{
  "current_block": 50123456,
  "start_block": 50000000,
  "end_block": 50500000,
  "total_events": 15432,
  "processed_events": 8234,
  "failed_events": 12,
  "unique_traders": ["0x123...", "0x456..."],
  "timestamp": "2024-01-15T10:30:00"
}
```

### Progress Output

```
Fetching events: 45%|████████      | 225000/500000 [05:23<06:34, 697.12blocks/s]
Processing trades: 32%|█████▎     | 4932/15432 [02:15<04:48, 36.32trades/s]
Updating trader stats: 67%|████████▋  | 1340/2000 [08:45<04:20, 2.54traders/s]
```

### Estimated Time

Script calculates and displays:
- Blocks per second
- Events per second
- Estimated time remaining
- Completion ETA

## Data Quality Report

After completion, generates `backfill_report_YYYYMMDD_HHMMSS.json`:

```json
{
  "backfill_summary": {
    "start_block": 50000000,
    "end_block": 50500000,
    "total_blocks": 500000,
    "total_events": 15432,
    "processed_events": 15420,
    "failed_events": 12,
    "unique_traders": 2345,
    "duration": "0:45:32"
  },
  "data_quality": {
    "success_rate": 99.92,
    "failure_rate": 0.08
  }
}
```

## Performance

### Expected Times

Based on default settings (90 days, batch size 1000):

| Metric | Estimated Value |
|--------|----------------|
| Total Blocks | ~3,888,000 (90 days × 43,200 blocks/day) |
| Total Events | ~10,000-50,000 (varies by activity) |
| Fetch Time | ~15-30 minutes |
| Process Time | ~10-20 minutes |
| Stats Calc | ~5-10 minutes |
| **Total** | **~30-60 minutes** |

### Optimization Tips

1. **Use Faster RPC**: QuickNode > Alchemy > Public
2. **Increase Batch Size**: For faster processing (more memory)
3. **Run During Low Traffic**: Less blockchain congestion
4. **Use Dedicated Database**: Avoid shared DB resources

## Troubleshooting

### Error: "RPC rate limit exceeded"

**Solution:**
```bash
# Use smaller batch size
python scripts/backfill_leaderboard.py --batch-size 500

# Or upgrade RPC provider plan
```

### Error: "Database connection timeout"

**Solution:**
```bash
# Increase database connection timeout in .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

### Script Interrupted

**Solution:**
```bash
# Always resume from checkpoint
python scripts/backfill_leaderboard.py --resume
```

### Memory Issues

**Solution:**
```bash
# Reduce batch size
python scripts/backfill_leaderboard.py --batch-size 500

# Or increase system memory limit
ulimit -v 8000000  # 8GB
```

## Post-Backfill Steps

### 1. Verify Data

```sql
-- Check total traders
SELECT COUNT(*) FROM traders;

-- Check P&L distribution
SELECT 
  COUNT(*) FILTER (WHERE pnl_total_usd > 0) as profitable,
  COUNT(*) FILTER (WHERE pnl_total_usd < 0) as unprofitable,
  COUNT(*) FILTER (WHERE pnl_total_usd = 0) as breakeven
FROM traders;

-- Top 10 traders
SELECT wallet_address, pnl_total_usd, total_trades
FROM traders
ORDER BY pnl_total_usd DESC
LIMIT 10;
```

### 2. Warm Up Cache

```bash
# Pre-populate Redis cache
curl http://localhost:8000/api/v1/leaderboard/top?limit=100
curl http://localhost:8000/api/v1/leaderboard/trending?limit=10
```

### 3. Start Background Jobs

```bash
# Start Celery workers for ongoing updates
celery -A app.workers.celery_app worker --loglevel=info

# Start beat scheduler
celery -A app.workers.celery_app beat --loglevel=info
```

### 4. Enable Leaderboard API

Update `app/api/v1/router.py`:
```python
from app.api.v1.endpoints import leaderboard

router.include_router(leaderboard.router)
```

## Advanced Usage

### Parallel Processing

```bash
# Use more workers (requires more memory)
python scripts/backfill_leaderboard.py --max-workers 8
```

### Custom Block Range

Edit script to specify exact blocks:
```python
backfill = HistoricalDataBackfill(days=90)
backfill.progress.start_block = 50000000
backfill.progress.end_block = 50500000
await backfill.run()
```

### Dry Run (Development)

Add `--dry-run` flag to test without database writes:
```python
parser.add_argument('--dry-run', action='store_true')
if args.dry_run:
    logger.info("DRY RUN MODE - No database writes")
```

## Monitoring

### Logs

Check logs in real-time:
```bash
tail -f backfill_*.log
```

### Database Metrics

Monitor during backfill:
```sql
-- Active connections
SELECT COUNT(*) FROM pg_stat_activity;

-- Table size
SELECT pg_size_pretty(pg_total_relation_size('traders'));

-- Insert rate
SELECT COUNT(*) FROM trades WHERE created_at > NOW() - INTERVAL '1 minute';
```

### System Resources

```bash
# CPU usage
top -p $(pgrep -f backfill_leaderboard)

# Memory usage
ps aux | grep backfill_leaderboard

# Disk I/O
iotop -p $(pgrep -f backfill_leaderboard)
```

## Deployment Checklist

- [ ] Database migrations applied
- [ ] RPC endpoints configured
- [ ] Sufficient database storage (estimate: ~100MB per 10k traders)
- [ ] Backup database before backfill
- [ ] Schedule during maintenance window
- [ ] Notify team of expected downtime (if any)
- [ ] Monitor progress via logs
- [ ] Verify data after completion
- [ ] Start background jobs
- [ ] Test leaderboard API endpoints

## Example: Initial Deployment

```bash
# 1. Prepare environment
cd backend
source venv/bin/activate
cp .env.example .env
# Edit .env with production values

# 2. Run migrations
alembic upgrade head

# 3. Run backfill (screen session for persistence)
screen -S backfill
python scripts/backfill_leaderboard.py --days 90 --verbose

# Detach: Ctrl+A, D
# Reattach: screen -r backfill

# 4. Wait for completion (~30-60 min)

# 5. Verify results
psql $DATABASE_URL -c "SELECT COUNT(*) FROM traders;"

# 6. Start workers
celery -A app.workers.celery_app worker -l info

# 7. Enable API
# (restart FastAPI service)
```

## Incremental Updates

After initial backfill, ongoing data collected via:
- Event listener (real-time)
- Background jobs (every 5 min)
- Daily snapshots

No need to re-run backfill unless:
- Database corruption
- Major schema changes
- Historical data corrections

## Support

For issues:
1. Check logs: `backfill_*.log`
2. Review checkpoint: `backfill_checkpoint.json`
3. Check database: `SELECT * FROM traders LIMIT 10;`
4. Resume if interrupted: `--resume`
