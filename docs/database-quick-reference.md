# Database Schema Quick Reference

## Table Summary

| Table | Rows (Est) | Purpose | Key Indexes |
|-------|-----------|---------|-------------|
| `users` | 10K - 100K | User accounts | email, wallet, tier |
| `polymarket_api_keys` | 20K - 200K | Encrypted credentials | user_id, status |
| `traders` | 1K - 10K | Leaderboard data | ranks, pnl, win_rate |
| `copy_relationships` | 50K - 500K | Copy configs | user_id, trader, status |
| `trades` (hypertable) | 1M - 100M+ | Trade history | timestamps, user, market |
| `trade_queue` | 1K - 10K | Pending trades | status+priority |

## Quick Reference

### Get Top 10 Traders
```sql
SELECT wallet_address, display_name, pnl_7d, win_rate, follower_count
FROM traders ORDER BY pnl_7d DESC LIMIT 10;
```

### Get User's Portfolio
```sql
SELECT * FROM v_user_portfolio WHERE user_id = $1;
```

### Get Active Copy Relationships
```sql
SELECT * FROM v_active_copy_relationships WHERE user_id = $1;
```

### Insert New Trade to Queue
```sql
INSERT INTO trade_queue (
    user_id, copy_relationship_id, trader_wallet_address,
    market_id, position, quantity, priority
) VALUES ($1, $2, $3, $4, $5, $6, 5);
```

### Get Next Pending Trade
```sql
SELECT * FROM trade_queue
WHERE status = 'pending'
ORDER BY priority ASC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

## Subscription Tier Limits

| Tier | Max Traders | Daily Trades | Trade Size | Total Exposure |
|------|------------|--------------|------------|----------------|
| Free | 3 | 10 | $100 | $500 |
| Basic | 10 | 50 | $500 | $2,500 |
| Pro | 25 | 200 | $2,000 | $10,000 |
| Premium | 100 | 1,000 | $10,000 | $100,000 |

## Trade Statuses

| Status | Description | Next Action |
|--------|-------------|-------------|
| `pending` | Trade created, not yet executed | Worker picks up |
| `open` | Trade executed, position open | Monitor for exit |
| `closed` | Position closed, P&L realized | Archive |
| `cancelled` | Trade cancelled before execution | No action |
| `failed` | Execution failed | Retry or alert |

## Common Queries

### User Dashboard Data
```sql
WITH user_stats AS (
    SELECT
        COUNT(*) FILTER (WHERE status = 'open') as open_positions,
        SUM(entry_value_usd) FILTER (WHERE status = 'open') as exposure,
        SUM(realized_pnl_usd) FILTER (WHERE status = 'closed') as total_pnl
    FROM trades
    WHERE copying_user_id = $1
)
SELECT 
    u.*,
    us.*,
    (SELECT COUNT(*) FROM copy_relationships WHERE user_id = $1 AND status = 'active') as following
FROM users u, user_stats us
WHERE u.id = $1;
```

### Trader Performance Calculation
```sql
UPDATE traders t SET
    win_rate = (winning_trades::decimal / NULLIF(total_trades, 0)) * 100,
    pnl_7d_percent = (pnl_7d / NULLIF(total_volume_usd, 0)) * 100,
    last_updated_at = NOW()
WHERE wallet_address = $1;
```

### Daily Reset for API Key Spend Limits
```sql
UPDATE polymarket_api_keys
SET daily_spent_usd = 0, last_reset_at = NOW()
WHERE last_reset_at < NOW() - INTERVAL '24 hours'
  AND status = 'active';
```

## Maintenance Tasks

### Clean Up Old Queue Entries
```sql
DELETE FROM trade_queue
WHERE (status = 'completed' AND completed_at < NOW() - INTERVAL '7 days')
   OR (status = 'failed' AND created_at < NOW() - INTERVAL '3 days')
   OR (expires_at < NOW());
```

### Recompute Trader Rankings
```sql
WITH ranked AS (
    SELECT 
        id,
        ROW_NUMBER() OVER (ORDER BY pnl_7d DESC) as new_rank_7d,
        ROW_NUMBER() OVER (ORDER BY total_pnl DESC) as new_rank_all,
        ROW_NUMBER() OVER (ORDER BY total_volume_usd DESC) as new_rank_vol
    FROM traders
    WHERE is_active = true
)
UPDATE traders t
SET 
    rank_7d = r.new_rank_7d,
    rank_all_time = r.new_rank_all,
    rank_volume = r.new_rank_vol,
    last_updated_at = NOW()
FROM ranked r
WHERE t.id = r.id;
```

## Monitoring Alerts

### Detect Stale Data
```sql
-- Traders not updated in > 1 hour
SELECT wallet_address, last_updated_at
FROM traders
WHERE last_updated_at < NOW() - INTERVAL '1 hour'
  AND is_active = true;

-- Trades stuck in 'processing'
SELECT *
FROM trade_queue
WHERE status = 'processing'
  AND started_at < NOW() - INTERVAL '5 minutes';
```

### High Volume Users
```sql
-- Users near daily limits
SELECT 
    u.email,
    u.max_daily_trades,
    COUNT(t.id) as trades_today
FROM users u
JOIN trades t ON u.id = t.copying_user_id
WHERE t.created_at > NOW() - INTERVAL '24 hours'
GROUP BY u.id, u.email, u.max_daily_trades
HAVING COUNT(t.id) >= u.max_daily_trades * 0.8;
```

## Performance Tips

1. **Use views for dashboards**: Reduces complex query writing
2. **Index on foreign keys**: Already done, but verify usage
3. **Partition trades table**: TimescaleDB automatic, configure compression
4. **Cache leaderboard**: Redis with 60s TTL
5. **Batch updates**: Update trader stats every 5 minutes, not per trade
