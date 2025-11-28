-- Initialize TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(42) UNIQUE NOT NULL,
    telegram_id BIGINT UNIQUE,
    email VARCHAR(255),
    username VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    tier VARCHAR(20) DEFAULT 'free',
    balance DECIMAL(20, 6) DEFAULT 0
);

-- Create API keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    encrypted_key BYTEA NOT NULL,
    key_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(user_id, key_type)
);

-- Create trades table (will become hypertable)
CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    trader_address VARCHAR(42) NOT NULL,
    market_id VARCHAR(66) NOT NULL,
    token_id VARCHAR(66) NOT NULL,
    side VARCHAR(10) NOT NULL,
    amount DECIMAL(20, 6) NOT NULL,
    price DECIMAL(10, 6) NOT NULL,
    tx_hash VARCHAR(66) UNIQUE,
    block_number BIGINT,
    timestamp TIMESTAMP NOT NULL,
    is_copy_trade BOOLEAN DEFAULT false,
    copied_from VARCHAR(42),
    outcome VARCHAR(10)
);

-- Convert to hypertable
SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);

-- Create indexes on trades
CREATE INDEX IF NOT EXISTS idx_trades_trader_timestamp ON trades (trader_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_market_timestamp ON trades (market_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_tx_hash ON trades (tx_hash);

-- Create copy relationships table
CREATE TABLE IF NOT EXISTS copy_relationships (
    id SERIAL PRIMARY KEY,
    follower_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    trader_address VARCHAR(42) NOT NULL,
    allocation_percentage DECIMAL(5, 2) DEFAULT 100.00,
    max_trade_size DECIMAL(20, 6),
    max_position_size DECIMAL(20, 6),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(follower_id, trader_address)
);

-- Create trader stats table
CREATE TABLE IF NOT EXISTS trader_stats (
    trader_address VARCHAR(42) PRIMARY KEY,
    total_trades INTEGER DEFAULT 0,
    total_volume DECIMAL(20, 6) DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0,
    avg_return DECIMAL(10, 4) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4) DEFAULT 0,
    max_drawdown DECIMAL(10, 4) DEFAULT 0,
    follower_count INTEGER DEFAULT 0,
    last_trade_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications (user_id, created_at DESC);

-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions (token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at);

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created ON audit_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_copy_relationships_updated_at BEFORE UPDATE ON copy_relationships
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trader_stats_updated_at BEFORE UPDATE ON trader_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
