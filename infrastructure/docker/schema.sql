-- =============================================================================
-- Polymarket Copy Trading Platform - Database Schema
-- =============================================================================
-- PostgreSQL 15+ with TimescaleDB and pgcrypto extensions
-- Creates tables for users, traders, trades, and copy relationships
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- TABLE: users
-- Stores authenticated users with subscription tiers and limits
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    
    -- Authentication
    email VARCHAR(255) UNIQUE,
    wallet_address VARCHAR(42) UNIQUE,
    telegram_id BIGINT UNIQUE,
    username VARCHAR(100),
    password_hash VARCHAR(255), -- bcrypt hash for email auth
    
    -- Subscription & Limits
    subscription_tier VARCHAR(20) NOT NULL DEFAULT 'free',
    -- Tier options: 'free', 'basic', 'pro', 'premium'
    
    max_followed_traders INTEGER NOT NULL DEFAULT 3,
    max_daily_trades INTEGER NOT NULL DEFAULT 10,
    max_trade_size_usd DECIMAL(12, 2) NOT NULL DEFAULT 100.00,
    max_total_exposure_usd DECIMAL(12, 2) NOT NULL DEFAULT 500.00,
    
    -- Balance & Spending
    balance_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    total_spent_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    total_earned_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    
    -- Status & Settings
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    two_factor_enabled BOOLEAN NOT NULL DEFAULT false,
    two_factor_secret VARCHAR(255),
    
    -- Notifications
    email_notifications BOOLEAN NOT NULL DEFAULT true,
    telegram_notifications BOOLEAN NOT NULL DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT users_wallet_format CHECK (wallet_address ~* '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT users_tier_valid CHECK (subscription_tier IN ('free', 'basic', 'pro', 'premium')),
    CONSTRAINT users_balance_positive CHECK (balance_usd >= 0)
);

-- Indexes for users table
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_wallet ON users(wallet_address) WHERE wallet_address IS NOT NULL;
CREATE INDEX idx_users_telegram ON users(telegram_id) WHERE telegram_id IS NOT NULL;
CREATE INDEX idx_users_tier ON users(subscription_tier);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

COMMENT ON TABLE users IS 'Platform users with authentication and subscription details';
COMMENT ON COLUMN users.subscription_tier IS 'User tier: free, basic, pro, premium';
COMMENT ON COLUMN users.max_followed_traders IS 'Maximum number of traders user can follow simultaneously';


-- =============================================================================
-- TABLE: polymarket_api_keys
-- Stores encrypted Polymarket API credentials with spend limits
-- =============================================================================
CREATE TABLE IF NOT EXISTS polymarket_api_keys (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Encrypted Credentials (using pgcrypto)
    encrypted_api_key BYTEA NOT NULL,
    encrypted_api_secret BYTEA NOT NULL,
    encrypted_private_key BYTEA, -- For direct contract interaction
    
    -- Key Metadata
    key_name VARCHAR(100), -- User-defined name for this key
    key_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash for lookup without decryption
    
    -- Spend Limits & Controls
    daily_spend_limit_usd DECIMAL(12, 2) NOT NULL DEFAULT 1000.00,
    daily_spent_usd DECIMAL(12, 2) NOT NULL DEFAULT 0,
    last_reset_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    total_trades_executed INTEGER NOT NULL DEFAULT 0,
    total_volume_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    
    -- Status & Security
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    -- Status options: 'active', 'revoked', 'suspended', 'expired'
    
    is_primary BOOLEAN NOT NULL DEFAULT false,
    
    -- Audit Trail
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    revoked_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT api_keys_status_valid CHECK (status IN ('active', 'revoked', 'suspended', 'expired')),
    CONSTRAINT api_keys_daily_limit_positive CHECK (daily_spend_limit_usd >= 0),
    CONSTRAINT api_keys_daily_spent_positive CHECK (daily_spent_usd >= 0),
    CONSTRAINT api_keys_one_primary_per_user UNIQUE (user_id, is_primary) WHERE is_primary = true
);

-- Indexes for polymarket_api_keys table
CREATE INDEX idx_api_keys_user_id ON polymarket_api_keys(user_id);
CREATE INDEX idx_api_keys_status ON polymarket_api_keys(status) WHERE status = 'active';
CREATE INDEX idx_api_keys_key_hash ON polymarket_api_keys(key_hash);
CREATE INDEX idx_api_keys_last_used ON polymarket_api_keys(last_used_at DESC);

COMMENT ON TABLE polymarket_api_keys IS 'Encrypted Polymarket API credentials with spend controls';
COMMENT ON COLUMN polymarket_api_keys.encrypted_api_key IS 'API key encrypted with pgcrypto';
COMMENT ON COLUMN polymarket_api_keys.key_hash IS 'SHA256 hash for key identification without decryption';
COMMENT ON COLUMN polymarket_api_keys.daily_spend_limit_usd IS 'Maximum USD spend per 24h period';


-- =============================================================================
-- TABLE: traders
-- Leaderboard data for tracked Polymarket traders
-- =============================================================================
CREATE TABLE IF NOT EXISTS traders (
    id BIGSERIAL PRIMARY KEY,
    wallet_address VARCHAR(42) UNIQUE NOT NULL,
    
    -- Performance Metrics (7-day rolling)
    pnl_7d DECIMAL(20, 6) NOT NULL DEFAULT 0,
    pnl_7d_percent DECIMAL(10, 4) NOT NULL DEFAULT 0,
    
    -- All-time Performance
    total_pnl DECIMAL(20, 6) NOT NULL DEFAULT 0,
    total_pnl_percent DECIMAL(10, 4) NOT NULL DEFAULT 0,
    total_volume_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    
    -- Trade Statistics
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0, -- Percentage: 0-100
    
    avg_trade_size_usd DECIMAL(12, 2) NOT NULL DEFAULT 0,
    avg_holding_time_hours DECIMAL(10, 2) NOT NULL DEFAULT 0,
    
    -- Risk Metrics
    sharpe_ratio DECIMAL(10, 4) DEFAULT 0,
    max_drawdown DECIMAL(10, 4) DEFAULT 0,
    volatility DECIMAL(10, 4) DEFAULT 0,
    
    -- Social Metrics
    follower_count INTEGER NOT NULL DEFAULT 0,
    total_copied_volume_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    
    -- Leaderboard
    rank_7d INTEGER,
    rank_all_time INTEGER,
    rank_volume INTEGER,
    
    -- Profile (optional)
    display_name VARCHAR(100),
    bio TEXT,
    avatar_url VARCHAR(500),
    
    -- Status
    is_verified BOOLEAN NOT NULL DEFAULT false,
    is_featured BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- Timestamps
    first_trade_at TIMESTAMP,
    last_trade_at TIMESTAMP,
    last_updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT traders_wallet_format CHECK (wallet_address ~* '^0x[a-fA-F0-9]{40}$'),
    CONSTRAINT traders_win_rate_range CHECK (win_rate >= 0 AND win_rate <= 100),
    CONSTRAINT traders_follower_count_positive CHECK (follower_count >= 0)
);

-- Indexes for traders table
CREATE INDEX idx_traders_wallet ON traders(wallet_address);
CREATE INDEX idx_traders_rank_7d ON traders(rank_7d) WHERE rank_7d IS NOT NULL;
CREATE INDEX idx_traders_rank_all_time ON traders(rank_all_time) WHERE rank_all_time IS NOT NULL;
CREATE INDEX idx_traders_pnl_7d ON traders(pnl_7d DESC);
CREATE INDEX idx_traders_total_pnl ON traders(total_pnl DESC);
CREATE INDEX idx_traders_win_rate ON traders(win_rate DESC);
CREATE INDEX idx_traders_follower_count ON traders(follower_count DESC);
CREATE INDEX idx_traders_last_trade ON traders(last_trade_at DESC);
CREATE INDEX idx_traders_is_active ON traders(is_active) WHERE is_active = true;

COMMENT ON TABLE traders IS 'Performance metrics and leaderboard data for Polymarket traders';
COMMENT ON COLUMN traders.pnl_7d IS '7-day profit/loss in USD';
COMMENT ON COLUMN traders.win_rate IS 'Percentage of winning trades (0-100)';
COMMENT ON COLUMN traders.sharpe_ratio IS 'Risk-adjusted return metric';


-- =============================================================================
-- TABLE: copy_relationships
-- Maps users to traders they are copying with configuration
-- =============================================================================
CREATE TABLE IF NOT EXISTS copy_relationships (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trader_wallet_address VARCHAR(42) NOT NULL,
    
    -- Copy Configuration
    proportionality_factor DECIMAL(8, 6) NOT NULL DEFAULT 0.01,
    -- 0.01 = 1% of trader's position size, 1.0 = 100%
    
    max_investment_per_trade_usd DECIMAL(12, 2) NOT NULL DEFAULT 100.00,
    max_total_exposure_usd DECIMAL(12, 2) NOT NULL DEFAULT 500.00,
    
    -- Risk Controls
    min_trade_size_usd DECIMAL(12, 2) DEFAULT 5.00,
    max_slippage_percent DECIMAL(5, 2) NOT NULL DEFAULT 1.00,
    stop_loss_percent DECIMAL(5, 2),
    take_profit_percent DECIMAL(5, 2),
    
    -- Market Filters
    allowed_markets TEXT[], -- Array of market IDs to copy (NULL = all)
    excluded_markets TEXT[], -- Array of market IDs to exclude
    
    -- Status & Statistics
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    -- Status options: 'active', 'paused', 'stopped'
    
    total_trades_copied INTEGER NOT NULL DEFAULT 0,
    total_invested_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    total_pnl_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    paused_at TIMESTAMP,
    last_trade_copied_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT copy_rel_unique UNIQUE (user_id, trader_wallet_address),
    CONSTRAINT copy_rel_status_valid CHECK (status IN ('active', 'paused', 'stopped')),
    CONSTRAINT copy_rel_proportionality_range CHECK (proportionality_factor > 0 AND proportionality_factor <= 10),
    CONSTRAINT copy_rel_max_investment_positive CHECK (max_investment_per_trade_usd >= 0),
    CONSTRAINT copy_rel_slippage_range CHECK (max_slippage_percent >= 0 AND max_slippage_percent <= 100),
    
    -- Foreign key to traders table
    CONSTRAINT fk_copy_rel_trader FOREIGN KEY (trader_wallet_address) 
        REFERENCES traders(wallet_address) ON DELETE CASCADE
);

-- Indexes for copy_relationships table
CREATE INDEX idx_copy_rel_user_id ON copy_relationships(user_id);
CREATE INDEX idx_copy_rel_trader_wallet ON copy_relationships(trader_wallet_address);
CREATE INDEX idx_copy_rel_status ON copy_relationships(status) WHERE status = 'active';
CREATE INDEX idx_copy_rel_user_status ON copy_relationships(user_id, status);
CREATE INDEX idx_copy_rel_created_at ON copy_relationships(created_at DESC);

COMMENT ON TABLE copy_relationships IS 'User-to-trader copy trading configurations';
COMMENT ON COLUMN copy_relationships.proportionality_factor IS 'Multiplier for trader position size (0.01 = 1%)';
COMMENT ON COLUMN copy_relationships.max_slippage_percent IS 'Maximum acceptable slippage percentage';


-- =============================================================================
-- TABLE: trades
-- Historical record of all executed trades (both original and copied)
-- TimescaleDB hypertable for time-series optimization
-- =============================================================================
CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL,
    
    -- Trade Identification
    original_tx_hash VARCHAR(66), -- Trader's transaction hash (if copied)
    copy_tx_hash VARCHAR(66) UNIQUE, -- Copying user's transaction hash
    
    -- Parties
    trader_wallet_address VARCHAR(42) NOT NULL,
    copying_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    copy_relationship_id BIGINT REFERENCES copy_relationships(id) ON DELETE SET NULL,
    
    -- Trade Classification
    is_copy_trade BOOLEAN NOT NULL DEFAULT false,
    trade_type VARCHAR(20) NOT NULL DEFAULT 'market',
    -- Trade types: 'market', 'limit', 'stop_loss', 'take_profit'
    
    -- Market Information
    market_id VARCHAR(100) NOT NULL,
    market_name VARCHAR(500),
    market_question TEXT,
    position VARCHAR(10) NOT NULL,
    -- Position: 'YES', 'NO', 'LONG', 'SHORT'
    
    -- Trade Details
    entry_price DECIMAL(20, 10) NOT NULL,
    exit_price DECIMAL(20, 10),
    quantity DECIMAL(20, 6) NOT NULL,
    
    -- Financials
    entry_value_usd DECIMAL(20, 6) NOT NULL,
    exit_value_usd DECIMAL(20, 6),
    fees_usd DECIMAL(20, 6) NOT NULL DEFAULT 0,
    gas_fee_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
    
    realized_pnl_usd DECIMAL(20, 6),
    realized_pnl_percent DECIMAL(10, 4),
    
    unrealized_pnl_usd DECIMAL(20, 6),
    current_value_usd DECIMAL(20, 6),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Status: 'pending', 'open', 'closed', 'cancelled', 'failed'
    
    failure_reason TEXT,
    
    -- Execution Details
    slippage_percent DECIMAL(5, 2),
    execution_time_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    entry_timestamp TIMESTAMP NOT NULL,
    exit_timestamp TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT trades_position_valid CHECK (position IN ('YES', 'NO', 'LONG', 'SHORT')),
    CONSTRAINT trades_status_valid CHECK (status IN ('pending', 'open', 'closed', 'cancelled', 'failed')),
    CONSTRAINT trades_quantity_positive CHECK (quantity > 0),
    CONSTRAINT trades_entry_value_positive CHECK (entry_value_usd > 0)
);

-- Create hypertable for time-series optimization
SELECT create_hypertable('trades', 'entry_timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');

-- Indexes for trades table
CREATE INDEX idx_trades_id ON trades(id DESC);
CREATE INDEX idx_trades_original_tx ON trades(original_tx_hash) WHERE original_tx_hash IS NOT NULL;
CREATE INDEX idx_trades_copy_tx ON trades(copy_tx_hash) WHERE copy_tx_hash IS NOT NULL;
CREATE INDEX idx_trades_trader_wallet ON trades(trader_wallet_address, entry_timestamp DESC);
CREATE INDEX idx_trades_copying_user ON trades(copying_user_id, entry_timestamp DESC) WHERE copying_user_id IS NOT NULL;
CREATE INDEX idx_trades_market ON trades(market_id, entry_timestamp DESC);
CREATE INDEX idx_trades_status ON trades(status, entry_timestamp DESC);
CREATE INDEX idx_trades_is_copy ON trades(is_copy_trade, entry_timestamp DESC);
CREATE INDEX idx_trades_entry_timestamp ON trades(entry_timestamp DESC);

COMMENT ON TABLE trades IS 'Historical record of all executed trades (TimescaleDB hypertable)';
COMMENT ON COLUMN trades.original_tx_hash IS 'Transaction hash of original trader (for copied trades)';
COMMENT ON COLUMN trades.copy_tx_hash IS 'Transaction hash of copying user';
COMMENT ON COLUMN trades.realized_pnl_usd IS 'Profit/loss after trade is closed';


-- =============================================================================
-- TABLE: trade_queue
-- Queue of pending trades to be executed by Celery workers
-- =============================================================================
CREATE TABLE IF NOT EXISTS trade_queue (
    id BIGSERIAL PRIMARY KEY,
    
    -- References
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    copy_relationship_id BIGINT NOT NULL REFERENCES copy_relationships(id) ON DELETE CASCADE,
    trader_wallet_address VARCHAR(42) NOT NULL,
    original_tx_hash VARCHAR(66),
    
    -- Trade Parameters
    market_id VARCHAR(100) NOT NULL,
    position VARCHAR(10) NOT NULL,
    quantity DECIMAL(20, 6) NOT NULL,
    target_price DECIMAL(20, 10),
    max_slippage_percent DECIMAL(5, 2) NOT NULL DEFAULT 1.00,
    
    -- Execution Control
    priority INTEGER NOT NULL DEFAULT 5,
    -- Priority: 1 (highest) to 10 (lowest)
    
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Status: 'pending', 'processing', 'completed', 'failed', 'cancelled'
    
    error_message TEXT,
    
    -- Celery Task
    celery_task_id VARCHAR(255) UNIQUE,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT trade_queue_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    CONSTRAINT trade_queue_priority_range CHECK (priority >= 1 AND priority <= 10),
    CONSTRAINT trade_queue_retry_count_positive CHECK (retry_count >= 0),
    CONSTRAINT trade_queue_quantity_positive CHECK (quantity > 0)
);

-- Indexes for trade_queue table
CREATE INDEX idx_trade_queue_status_priority ON trade_queue(status, priority, created_at) 
    WHERE status IN ('pending', 'processing');
CREATE INDEX idx_trade_queue_user_id ON trade_queue(user_id, created_at DESC);
CREATE INDEX idx_trade_queue_celery_task ON trade_queue(celery_task_id) WHERE celery_task_id IS NOT NULL;
CREATE INDEX idx_trade_queue_expires_at ON trade_queue(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_trade_queue_created_at ON trade_queue(created_at DESC);

COMMENT ON TABLE trade_queue IS 'Queue of pending trades for Celery worker execution';
COMMENT ON COLUMN trade_queue.priority IS 'Execution priority: 1 (highest) to 10 (lowest)';
COMMENT ON COLUMN trade_queue.celery_task_id IS 'UUID of Celery task processing this trade';


-- =============================================================================
-- TRIGGERS: Auto-update timestamps
-- =============================================================================

-- Generic function to update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON polymarket_api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_copy_rel_updated_at BEFORE UPDATE ON copy_relationships
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =============================================================================
-- VIEWS: Useful aggregations and queries
-- =============================================================================

-- Active copy relationships with trader details
CREATE OR REPLACE VIEW v_active_copy_relationships AS
SELECT 
    cr.id,
    cr.user_id,
    u.email AS user_email,
    u.wallet_address AS user_wallet,
    cr.trader_wallet_address,
    t.display_name AS trader_name,
    t.win_rate AS trader_win_rate,
    t.pnl_7d AS trader_pnl_7d,
    cr.proportionality_factor,
    cr.max_investment_per_trade_usd,
    cr.total_trades_copied,
    cr.total_pnl_usd,
    cr.created_at
FROM copy_relationships cr
JOIN users u ON cr.user_id = u.id
JOIN traders t ON cr.trader_wallet_address = t.wallet_address
WHERE cr.status = 'active' AND u.is_active = true;

-- User portfolio summary
CREATE OR REPLACE VIEW v_user_portfolio AS
SELECT 
    u.id AS user_id,
    u.email,
    u.subscription_tier,
    u.balance_usd,
    COUNT(DISTINCT cr.id) AS traders_following,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'open') AS open_positions,
    SUM(t.entry_value_usd) FILTER (WHERE t.status = 'open') AS total_exposure_usd,
    SUM(t.realized_pnl_usd) FILTER (WHERE t.status = 'closed') AS total_realized_pnl,
    SUM(t.unrealized_pnl_usd) FILTER (WHERE t.status = 'open') AS total_unrealized_pnl
FROM users u
LEFT JOIN copy_relationships cr ON u.id = cr.user_id AND cr.status = 'active'
LEFT JOIN trades t ON u.id = t.copying_user_id
WHERE u.is_active = true
GROUP BY u.id, u.email, u.subscription_tier, u.balance_usd;

COMMENT ON VIEW v_active_copy_relationships IS 'Active copy relationships with trader performance data';
COMMENT ON VIEW v_user_portfolio IS 'Summary of user portfolio and positions';


-- =============================================================================
-- SAMPLE DATA (for development/testing only)
-- =============================================================================
-- Uncomment to insert sample data

/*
-- Sample users
INSERT INTO users (email, wallet_address, subscription_tier, balance_usd) VALUES
('alice@example.com', '0x1234567890123456789012345678901234567890', 'pro', 1000.00),
('bob@example.com', '0x2345678901234567890123456789012345678901', 'free', 100.00);

-- Sample traders
INSERT INTO traders (wallet_address, display_name, pnl_7d, total_pnl, total_trades, winning_trades, win_rate, follower_count) VALUES
('0xABCDEF1234567890ABCDEF1234567890ABCDEF12', 'ProTrader', 500.00, 2500.00, 100, 65, 65.00, 15),
('0x9876543210987654321098765432109876543210', 'MarketMaker', 300.00, 1500.00, 80, 56, 70.00, 8);
*/

-- =============================================================================
-- End of schema creation
-- =============================================================================
