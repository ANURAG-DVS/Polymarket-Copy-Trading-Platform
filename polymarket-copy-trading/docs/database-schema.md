# Database Schema Documentation

## Overview

The Polymarket Copy Trading Platform uses PostgreSQL 15+ with TimescaleDB extension for time-series optimization. The schema consists of 6 core tables with proper relationships, constraints, and indexes.

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USERS                                       │
├──────────┬──────────────────────────────────────────────────────────────┤
│ PK       │ id (BIGSERIAL)                                               │
│ UNIQUE   │ email, wallet_address, telegram_id                           │
│          │ subscription_tier (free/basic/pro/premium)                   │
│          │ max_followed_traders, max_daily_trades                       │
│          │ balance_usd, is_active, created_at                           │
└──────────┴────────────┬────────────────────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
┌────────────────┐ ┌────────────┐ ┌───────────────┐
│ API_KEYS       │ │ COPY_REL   │ │ TRADE_QUEUE   │
├────────────────┤ ├────────────┤ ├───────────────┤
│ PK: id         │ │ PK: id     │ │ PK: id        │
│ FK: user_id    │ │ FK: user_id│ │ FK: user_id   │
│ encrypted_key  │ │ FK: trader │ │ FK: copy_rel  │
│ status         │ │ proportion │ │ status        │
│ spend_limit    │ │ max_invest │ │ priority      │
└────────────────┘ └─────┬──────┘ └───────────────┘
                         │
                         │
                    ┌────┴─────┐
                    ▼          ▼
         ┌──────────────┐  ┌──────────────┐
         │   TRADERS    │  │   TRADES     │
         ├──────────────┤  ├──────────────┤
         │ PK: id       │  │ id (BIGSERIAL│
         │ UNIQUE: addr │  │ HYPERTABLE)  │
         │ pnl_7d       │  │ FK: user_id  │
         │ total_pnl    │  │ FK: copy_rel │
         │ win_rate     │  │ trader_addr  │
         │ rank_7d      │  │ market_id    │
         │ follower_cnt │  │ entry/exit   │
         └──────────────┘  │ pnl_realized │
                           │ status       │
                           │ timestamps   │
                           └──────────────┘
```

## Table Relationships

### 1:N Relationships
- **users → polymarket_api_keys**: One user can have multiple API keys
- **users → copy_relationships**: One user can follow multiple traders
- **users → trade_queue**: One user can have multiple pending trades
- **traders → copy_relationships**: One trader can have multiple followers
- **copy_relationships → trades**: One relationship generates many trades

### Special Relationships
- **traders.wallet_address ← copy_relationships.trader_wallet_address**: Foreign key on wallet address
- **trades.entry_timestamp (HYPERTABLE)**: TimescaleDB time-series partitioning

## Table Details

### 1. users

**Purpose**: Store authenticated users with subscription tiers and limits

**Key Columns**:
- `id`: Primary key (BIGSERIAL)
- `email, wallet_address, telegram_id`: Unique authentication methods
- `subscription_tier`: Enum ('free', 'basic', 'pro', 'premium')
- `max_followed_traders`: Tier-based limit (default: 3 for free)
- `max_daily_trades`: Daily trade limit (default: 10)
- `max_trade_size_usd`: Per-trade USD limit
- `balance_usd`: User's available balance
- `two_factor_enabled, two_factor_secret`: 2FA authentication

**Indexes**:
- `idx_users_email`: Email lookup (partial: WHERE email IS NOT NULL)
- `idx_users_wallet`: Wallet address lookup
- `idx_users_tier`: Filter by subscription tier
- `idx_users_created_at`: Time-based queries (DESC)

**Constraints**:
- Email format validation (regex)
- Wallet address format (0x + 40 hex chars)
- Balance must be >= 0
- Valid subscription tier values

---

### 2. polymarket_api_keys

**Purpose**: Store encrypted Polymarket API credentials with spend controls

**Key Columns**:
- `encrypted_api_key, encrypted_api_secret`: BYTEA (pgcrypto encrypted)
- `encrypted_private_key`: Optional for direct contract interaction
- `key_hash`: SHA256 hash for lookup without decryption
- `daily_spend_limit_usd`: Maximum USD spend per 24h
- `daily_spent_usd`: Current 24h spend (resets at `last_reset_at`)
- `status`: Enum ('active', 'revoked', 'suspended', 'expired')
- `is_primary`: Only one primary key per user

**Security**:
- All sensitive data encrypted at rest using pgcrypto
- Key hash for identification without decryption
- Audit trail: `last_used_at`, `revoked_at`, `revoked_reason`

**Indexes**:
- `idx_api_keys_user_id`: All keys for a user
- `idx_api_keys_status`: Active keys only (partial)
- `idx_api_keys_key_hash`: Fast lookup by hash

**Unique Constraints**:
- `(user_id, is_primary) WHERE is_primary = true`: Only one primary key per user

---

### 3. traders

**Purpose**: Leaderboard data for tracked Polymarket traders

**Key Columns**:
- `wallet_address`: Unique trader identifier (0x...)
- `pnl_7d, pnl_7d_percent`: 7-day rolling profit/loss
- `total_pnl, total_pnl_percent`: All-time performance
- `total_trades, winning_trades, losing_trades`: Trade statistics
- `win_rate`: Percentage (0-100)
- `sharpe_ratio, max_drawdown, volatility`: Risk metrics
- `follower_count`: Number of users copying this trader
- `rank_7d, rank_all_time, rank_volume`: Leaderboard positions
- `is_verified, is_featured`: Platform status flags

**Performance Metrics**:
- **7-day metrics**: Rolling window for recent performance
- **All-time metrics**: Complete trading history
- **Risk metrics**: Sharpe ratio, drawdown, volatility
- **Social proof**: Follower count, copied volume

**Indexes**:
- `idx_traders_rank_7d`: Leaderboard queries (partial: WHERE rank_7d IS NOT NULL)
- `idx_traders_pnl_7d`: Sort by 7-day profit (DESC)
- `idx_traders_win_rate`: Sort by win rate (DESC)
- `idx_traders_follower_count`: Most followed traders (DESC)

---

### 4. copy_relationships

**Purpose**: User-to-trader copy trading configurations

**Key Columns**:
- `user_id, trader_wallet_address`: Composite relationship
- `proportionality_factor`: Multiplier (0.01 = 1% of trader's size)
- `max_investment_per_trade_usd`: Per-trade limit
- `max_total_exposure_usd`: Total position size limit
- `max_slippage_percent`: Acceptable slippage (default: 1%)
- `stop_loss_percent, take_profit_percent`: Auto-close triggers
- `allowed_markets, excluded_markets`: TEXT[] arrays for filtering
- `status`: Enum ('active', 'paused', 'stopped')

**Risk Controls**:
- Position sizing via proportionality factor
- Per-trade and total exposure limits
- Slippage protection
- Stop loss / take profit automation
- Market filtering (whitelist/blacklist)

**Indexes**:
- `idx_copy_rel_user_id`: All relationships for a user
- `idx_copy_rel_trader_wallet`: All followers of a trader
- `idx_copy_rel_status`: Active relationships only (partial)
- `idx_copy_rel_user_status`: Combined user + status filter

**Unique Constraint**:
- `(user_id, trader_wallet_address)`: One relationship per user-trader pair

---

### 5. trades (TimescaleDB Hypertable)

**Purpose**: Historical record of all executed trades

**Key Columns**:
- `original_tx_hash`: Trader's transaction hash (for copied trades)
- `copy_tx_hash`: Copying user's transaction hash (UNIQUE)
- `trader_wallet_address, copying_user_id`: Both parties
- `is_copy_trade`: Boolean flag
- `market_id, market_name, position`: Trade details
- `entry_price, exit_price, quantity`: Pricing
- `entry_value_usd, exit_value_usd`: USD values
- `realized_pnl_usd, unrealized_pnl_usd`: Profit/loss
- `status`: Enum ('pending', 'open', 'closed', 'cancelled', 'failed')
- `entry_timestamp, exit_timestamp`: Time-series keys

**TimescaleDB Optimization**:
- Hypertable partitioned by `entry_timestamp`
- Chunk interval: 7 days
- Automatic data retention policies (can be configured)
- Optimized for time-range queries

**Indexes**:
- `idx_trades_trader_wallet`: Trader's trade history
- `idx_trades_copying_user`: User's copied trades
- `idx_trades_market`: Market-specific trades
- `idx_trades_status`: Filter by status
- `idx_trades_entry_timestamp`: Time-based queries (DESC)

**P&L Calculation**:
- `realized_pnl_usd = exit_value_usd - entry_value_usd - fees_usd - gas_fee_usd`
- `realized_pnl_percent = (realized_pnl_usd / entry_value_usd) * 100`
- `unrealized_pnl_usd = current_value_usd - entry_value_usd`

---

### 6. trade_queue

**Purpose**: Queue of pending trades for Celery worker execution

**Key Columns**:
- `user_id, copy_relationship_id`: Source of trade
- `trader_wallet_address, original_tx_hash`: Reference to original trade
- `market_id, position, quantity`: Trade parameters
- `priority`: 1-10 (1 = highest priority)
- `retry_count, max_retries`: Retry logic
- `status`: Enum ('pending', 'processing', 'completed', 'failed', 'cancelled')
- `celery_task_id`: UUID of Celery task
- `scheduled_for, expires_at`: Timing controls

**Execution Flow**:
1. Trade detected → Insert into queue with `status='pending'`
2. Celery worker picks up → Update `status='processing'`, set `celery_task_id`
3. On success → Update `status='completed'`, insert into `trades` table
4. On failure → Increment `retry_count`, retry if < `max_retries`
5. On expiration → Update `status='cancelled'`

**Indexes**:
- `idx_trade_queue_status_priority`: Worker pickup (partial: pending/processing)
- `idx_trade_queue_celery_task`: Task status lookup
- `idx_trade_queue_expires_at`: Cleanup expired tasks

---

## Views

### v_active_copy_relationships

**Purpose**: Active copy relationships with trader details

**Columns**:
- User info: `user_id, user_email, user_wallet`
- Trader info: `trader_wallet_address, trader_name, trader_win_rate, trader_pnl_7d`
- Config: `proportionality_factor, max_investment_per_trade_usd`
- Stats: `total_trades_copied, total_pnl_usd`

**Usage**: Dashboard view of who is copying whom

---

### v_user_portfolio

**Purpose**: User portfolio summary with aggregated stats

**Columns**:
- User: `user_id, email, subscription_tier, balance_usd`
- Following: `traders_following` (count)
- Positions: `open_positions`, `total_exposure_usd`
- P&L: `total_realized_pnl`, `total_unrealized_pnl`

**Usage**: Portfolio overview page

---

## Triggers

### update_updated_at_column()

**Tables**: users, polymarket_api_keys, copy_relationships, trades

**Function**: Automatically updates `updated_at` column on any UPDATE operation

**Implementation**:
```sql
CREATE TRIGGER update_users_updated_at 
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Indexing Strategy

### Performance Optimizations

1. **Partial Indexes**: Used for filtered queries (e.g., active users only)
   ```sql
   CREATE INDEX idx_users_email ON users(email) 
   WHERE email IS NOT NULL;
   ```

2. **Composite Indexes**: For multi-column queries
   ```sql
   CREATE INDEX idx_copy_rel_user_status 
   ON copy_relationships(user_id, status);
   ```

3. **DESC Indexes**: For leaderboard/sorting queries
   ```sql
   CREATE INDEX idx_traders_pnl_7d 
   ON traders(pnl_7d DESC);
   ```

4. **TimescaleDB Hypertable**: Automatic partitioning for `trades` table
   - 7-day chunks for optimal time-range queries
   - Compression policies for old data (configurable)

---

## Security Features

### Encryption

- **API Keys**: `pgcrypto` extension for at-rest encryption
- **Key Hash**: SHA256 for lookup without decryption
- **Environment-based master key**: For application-level encryption

### Constraints

- **Email validation**: Regex check for valid format
- **Wallet validation**: 0x + 40 hex characters
- **Balance checks**: Prevent negative balances
- **Enum validation**: Strict value checking for status fields

### Audit Trail

- All tables have `created_at` and `updated_at` timestamps
- API keys track: `last_used_at`, `revoked_at`, `revoked_reason`
- Trade queue tracks retry attempts and errors

---

## Migration Usage

### Apply Migration

```bash
# Using Alembic
cd backend
alembic upgrade head

# Using raw SQL
psql -U postgres -d polymarket_copy < infrastructure/docker/schema.sql
```

### Rollback Migration

```bash
# Using Alembic
alembic downgrade -1

# Manual rollback (WARNING: deletes all data)
# See downgrade() function in migration file
```

---

## Sample Queries

### Get Leaderboard (Top 10 traders by 7-day P&L)

```sql
SELECT 
    wallet_address,
    display_name,
    pnl_7d,
    win_rate,
    total_trades,
    follower_count
FROM traders
WHERE is_active = true
ORDER BY pnl_7d DESC
LIMIT 10;
```

### Get User's Active Positions

```sql
SELECT 
    t.market_name,
    t.position,
    t.quantity,
    t.entry_value_usd,
    t.current_value_usd,
    t.unrealized_pnl_usd,
    t.entry_timestamp
FROM trades t
WHERE t.copying_user_id = $1
  AND t.status = 'open'
ORDER BY t.entry_timestamp DESC;
```

### Get Trader's Followers

```sql
SELECT 
    u.email,
    u.wallet_address,
    cr.proportionality_factor,
    cr.total_trades_copied,
    cr.total_pnl_usd,
    cr.created_at
FROM copy_relationships cr
JOIN users u ON cr.user_id = u.id
WHERE cr.trader_wallet_address = $1
  AND cr.status = 'active'
ORDER BY cr.created_at DESC;
```

### Get Pending Trades in Queue

```sql
SELECT 
    tq.id,
    u.email,
    tq.market_id,
    tq.position,
    tq.quantity,
    tq.priority,
    tq.created_at
FROM trade_queue tq
JOIN users u ON tq.user_id = u.id
WHERE tq.status = 'pending'
ORDER BY tq.priority ASC, tq.created_at ASC
LIMIT 100;
```

---

## Performance Considerations

### Expected Query Patterns

1. **Leaderboard queries**: Frequent, read-heavy
   - Indexed by `pnl_7d`, `win_rate`, `follower_count` (DESC)
   - Consider materialized view for top 100

2. **User portfolio**: Per-user, moderate frequency
   - View already optimized with aggregations
   - Consider Redis cache with 1-minute TTL

3. **Trade history**: Time-range queries
   - TimescaleDB hypertable optimized for this
   - Automatic compression after 30 days (configurable)

4. **Trade queue**: High-frequency writes/updates
   - Workers poll every second
   - Partial index on `status IN ('pending', 'processing')`

### Scaling Recommendations

- **Read replicas**: For leaderboard and historical data
- **Connection pooling**: PgBouncer with 20-50 connections
- **TimescaleDB compression**: Enable after 30 days for trades table
- **Redis caching**: Leaderboard, user portfolios, trader stats
- **Partitioning**: trade_queue by created_at if > 1M rows

---

## Data Retention

### Recommended Policies

```sql
-- Compress trades older than 30 days
SELECT add_compression_policy('trades', INTERVAL '30 days');

-- Drop trade_queue entries older than 7 days
DELETE FROM trade_queue 
WHERE completed_at < NOW() - INTERVAL '7 days'
   OR (created_at < NOW() - INTERVAL '7 days' AND status = 'failed');

-- Archive closed trades older than 1 year (optional)
-- Move to separate archive table or S3
```

---

## Backup Strategy

### Recommended Approach

1. **Daily full backups**: Entire database
2. **WAL archiving**: Point-in-time recovery
3. **TimescaleDB continuous aggregates**: Pre-computed leaderboards
4. **Offsite storage**: AWS S3 or equivalent

```bash
# Full backup
pg_dump -Fc polymarket_copy > backup_$(date +%Y%m%d).dump

# Restore
pg_restore -d polymarket_copy backup_20251128.dump
```

---

## Monitoring Queries

### Table Sizes

```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Index Usage

```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC;
```

### Slow Queries

```sql
-- Enable pg_stat_statements extension
CREATE EXTENSION pg_stat_statements;

-- View slowest queries
SELECT 
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## Schema Version

- **Version**: 001_initial_schema
- **Created**: 2025-11-28
- **PostgreSQL**: 15+
- **Extensions**: timescaledb, pgcrypto, uuid-ossp
