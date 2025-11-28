"""Initial database schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-11-28 23:47:00

Creates the complete database schema for Polymarket copy trading platform:
- users table with authentication and subscription
- polymarket_api_keys table with encrypted credentials
- traders table for leaderboard data
- copy_relationships table for user-trader mappings
- trades table (TimescaleDB hypertable) for trade history
- trade_queue table for pending trades
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables and related objects"""
    
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # =========================================================================
    # TABLE: users
    # =========================================================================
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('wallet_address', sa.String(42), nullable=True),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        
        sa.Column('subscription_tier', sa.String(20), nullable=False, server_default='free'),
        sa.Column('max_followed_traders', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_daily_trades', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_trade_size_usd', sa.Numeric(12, 2), nullable=False, server_default='100.00'),
        sa.Column('max_total_exposure_usd', sa.Numeric(12, 2), nullable=False, server_default='500.00'),
        
        sa.Column('balance_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('total_spent_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('total_earned_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('two_factor_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('two_factor_secret', sa.String(255), nullable=True),
        
        sa.Column('email_notifications', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('telegram_notifications', sa.Boolean(), nullable=False, server_default='true'),
        
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_login_at', sa.TIMESTAMP(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('wallet_address'),
        sa.UniqueConstraint('telegram_id'),
        sa.CheckConstraint("subscription_tier IN ('free', 'basic', 'pro', 'premium')", name='users_tier_valid'),
        sa.CheckConstraint('balance_usd >= 0', name='users_balance_positive'),
    )
    
    # Users indexes
    op.create_index('idx_users_email', 'users', ['email'], postgresql_where=sa.text('email IS NOT NULL'))
    op.create_index('idx_users_wallet', 'users', ['wallet_address'], postgresql_where=sa.text('wallet_address IS NOT NULL'))
    op.create_index('idx_users_telegram', 'users', ['telegram_id'], postgresql_where=sa.text('telegram_id IS NOT NULL'))
    op.create_index('idx_users_tier', 'users', ['subscription_tier'])
    op.create_index('idx_users_created_at', 'users', [sa.text('created_at DESC')])
    
    # =========================================================================
    # TABLE: polymarket_api_keys
    # =========================================================================
    op.create_table(
        'polymarket_api_keys',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        
        sa.Column('encrypted_api_key', sa.LargeBinary(), nullable=False),
        sa.Column('encrypted_api_secret', sa.LargeBinary(), nullable=False),
        sa.Column('encrypted_private_key', sa.LargeBinary(), nullable=True),
        
        sa.Column('key_name', sa.String(100), nullable=True),
        sa.Column('key_hash', sa.String(64), nullable=False),
        
        sa.Column('daily_spend_limit_usd', sa.Numeric(12, 2), nullable=False, server_default='1000.00'),
        sa.Column('daily_spent_usd', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('last_reset_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        
        sa.Column('total_trades_executed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_volume_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        
        sa.Column('last_used_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('revoked_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('revoked_reason', sa.Text(), nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('key_hash'),
        sa.CheckConstraint("status IN ('active', 'revoked', 'suspended', 'expired')", name='api_keys_status_valid'),
        sa.CheckConstraint('daily_spend_limit_usd >= 0', name='api_keys_daily_limit_positive'),
    )
    
    # API keys indexes
    op.create_index('idx_api_keys_user_id', 'polymarket_api_keys', ['user_id'])
    op.create_index('idx_api_keys_status', 'polymarket_api_keys', ['status'], postgresql_where=sa.text("status = 'active'"))
    op.create_index('idx_api_keys_key_hash', 'polymarket_api_keys', ['key_hash'])
    op.create_index('idx_api_keys_last_used', 'polymarket_api_keys', [sa.text('last_used_at DESC')])
    
    # =========================================================================
    # TABLE: traders
    # =========================================================================
    op.create_table(
        'traders',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('wallet_address', sa.String(42), nullable=False),
        
        sa.Column('pnl_7d', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('pnl_7d_percent', sa.Numeric(10, 4), nullable=False, server_default='0'),
        
        sa.Column('total_pnl', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('total_pnl_percent', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('total_volume_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('winning_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('losing_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('win_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),
        
        sa.Column('avg_trade_size_usd', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('avg_holding_time_hours', sa.Numeric(10, 2), nullable=False, server_default='0'),
        
        sa.Column('sharpe_ratio', sa.Numeric(10, 4), nullable=True, server_default='0'),
        sa.Column('max_drawdown', sa.Numeric(10, 4), nullable=True, server_default='0'),
        sa.Column('volatility', sa.Numeric(10, 4), nullable=True, server_default='0'),
        
        sa.Column('follower_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_copied_volume_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        
        sa.Column('rank_7d', sa.Integer(), nullable=True),
        sa.Column('rank_all_time', sa.Integer(), nullable=True),
        sa.Column('rank_volume', sa.Integer(), nullable=True),
        
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        
        sa.Column('first_trade_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_trade_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wallet_address'),
        sa.CheckConstraint('win_rate >= 0 AND win_rate <= 100', name='traders_win_rate_range'),
        sa.CheckConstraint('follower_count >= 0', name='traders_follower_count_positive'),
    )
    
    # Traders indexes
    op.create_index('idx_traders_wallet', 'traders', ['wallet_address'])
    op.create_index('idx_traders_rank_7d', 'traders', ['rank_7d'], postgresql_where=sa.text('rank_7d IS NOT NULL'))
    op.create_index('idx_traders_rank_all_time', 'traders', ['rank_all_time'], postgresql_where=sa.text('rank_all_time IS NOT NULL'))
    op.create_index('idx_traders_pnl_7d', 'traders', [sa.text('pnl_7d DESC')])
    op.create_index('idx_traders_total_pnl', 'traders', [sa.text('total_pnl DESC')])
    op.create_index('idx_traders_win_rate', 'traders', [sa.text('win_rate DESC')])
    op.create_index('idx_traders_follower_count', 'traders', [sa.text('follower_count DESC')])
    op.create_index('idx_traders_last_trade', 'traders', [sa.text('last_trade_at DESC')])
    op.create_index('idx_traders_is_active', 'traders', ['is_active'], postgresql_where=sa.text('is_active = true'))
    
    # =========================================================================
    # TABLE: copy_relationships
    # =========================================================================
    op.create_table(
        'copy_relationships',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('trader_wallet_address', sa.String(42), nullable=False),
        
        sa.Column('proportionality_factor', sa.Numeric(8, 6), nullable=False, server_default='0.01'),
        sa.Column('max_investment_per_trade_usd', sa.Numeric(12, 2), nullable=False, server_default='100.00'),
        sa.Column('max_total_exposure_usd', sa.Numeric(12, 2), nullable=False, server_default='500.00'),
        
        sa.Column('min_trade_size_usd', sa.Numeric(12, 2), nullable=True, server_default='5.00'),
        sa.Column('max_slippage_percent', sa.Numeric(5, 2), nullable=False, server_default='1.00'),
        sa.Column('stop_loss_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('take_profit_percent', sa.Numeric(5, 2), nullable=True),
        
        sa.Column('allowed_markets', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('excluded_markets', postgresql.ARRAY(sa.Text()), nullable=True),
        
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        
        sa.Column('total_trades_copied', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_invested_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('total_pnl_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('paused_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_trade_copied_at', sa.TIMESTAMP(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trader_wallet_address'], ['traders.wallet_address'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'trader_wallet_address', name='copy_rel_unique'),
        sa.CheckConstraint("status IN ('active', 'paused', 'stopped')", name='copy_rel_status_valid'),
        sa.CheckConstraint('proportionality_factor > 0 AND proportionality_factor <= 10', name='copy_rel_proportionality_range'),
    )
    
    # Copy relationships indexes
    op.create_index('idx_copy_rel_user_id', 'copy_relationships', ['user_id'])
    op.create_index('idx_copy_rel_trader_wallet', 'copy_relationships', ['trader_wallet_address'])
    op.create_index('idx_copy_rel_status', 'copy_relationships', ['status'], postgresql_where=sa.text("status = 'active'"))
    op.create_index('idx_copy_rel_user_status', 'copy_relationships', ['user_id', 'status'])
    op.create_index('idx_copy_rel_created_at', 'copy_relationships', [sa.text('created_at DESC')])
    
    # =========================================================================
    # TABLE: trades
    # =========================================================================
    op.create_table(
        'trades',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        
        sa.Column('original_tx_hash', sa.String(66), nullable=True),
        sa.Column('copy_tx_hash', sa.String(66), nullable=True),
        
        sa.Column('trader_wallet_address', sa.String(42), nullable=False),
        sa.Column('copying_user_id', sa.BigInteger(), nullable=True),
        sa.Column('copy_relationship_id', sa.BigInteger(), nullable=True),
        
        sa.Column('is_copy_trade', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trade_type', sa.String(20), nullable=False, server_default='market'),
        
        sa.Column('market_id', sa.String(100), nullable=False),
        sa.Column('market_name', sa.String(500), nullable=True),
        sa.Column('market_question', sa.Text(), nullable=True),
        sa.Column('position', sa.String(10), nullable=False),
        
        sa.Column('entry_price', sa.Numeric(20, 10), nullable=False),
        sa.Column('exit_price', sa.Numeric(20, 10), nullable=True),
        sa.Column('quantity', sa.Numeric(20, 6), nullable=False),
        
        sa.Column('entry_value_usd', sa.Numeric(20, 6), nullable=False),
        sa.Column('exit_value_usd', sa.Numeric(20, 6), nullable=True),
        sa.Column('fees_usd', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('gas_fee_usd', sa.Numeric(12, 6), nullable=False, server_default='0'),
        
        sa.Column('realized_pnl_usd', sa.Numeric(20, 6), nullable=True),
        sa.Column('realized_pnl_percent', sa.Numeric(10, 4), nullable=True),
        sa.Column('unrealized_pnl_usd', sa.Numeric(20, 6), nullable=True),
        sa.Column('current_value_usd', sa.Numeric(20, 6), nullable=True),
        
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        
        sa.Column('slippage_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('entry_timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('exit_timestamp', sa.TIMESTAMP(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        
        sa.ForeignKeyConstraint(['copying_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['copy_relationship_id'], ['copy_relationships.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('copy_tx_hash'),
        sa.CheckConstraint("position IN ('YES', 'NO', 'LONG', 'SHORT')", name='trades_position_valid'),
        sa.CheckConstraint("status IN ('pending', 'open', 'closed', 'cancelled', 'failed')", name='trades_status_valid'),
        sa.CheckConstraint('quantity > 0', name='trades_quantity_positive'),
    )
    
    # Create TimescaleDB hypertable
    op.execute("SELECT create_hypertable('trades', 'entry_timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days')")
    
    # Trades indexes
    op.create_index('idx_trades_id', 'trades', [sa.text('id DESC')])
    op.create_index('idx_trades_original_tx', 'trades', ['original_tx_hash'], postgresql_where=sa.text('original_tx_hash IS NOT NULL'))
    op.create_index('idx_trades_copy_tx', 'trades', ['copy_tx_hash'], postgresql_where=sa.text('copy_tx_hash IS NOT NULL'))
    op.create_index('idx_trades_trader_wallet', 'trades', ['trader_wallet_address', sa.text('entry_timestamp DESC')])
    op.create_index('idx_trades_copying_user', 'trades', ['copying_user_id', sa.text('entry_timestamp DESC')], postgresql_where=sa.text('copying_user_id IS NOT NULL'))
    op.create_index('idx_trades_market', 'trades', ['market_id', sa.text('entry_timestamp DESC')])
    op.create_index('idx_trades_status', 'trades', ['status', sa.text('entry_timestamp DESC')])
    op.create_index('idx_trades_is_copy', 'trades', ['is_copy_trade', sa.text('entry_timestamp DESC')])
    op.create_index('idx_trades_entry_timestamp', 'trades', [sa.text('entry_timestamp DESC')])
    
    # =========================================================================
    # TABLE: trade_queue
    # =========================================================================
    op.create_table(
        'trade_queue',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('copy_relationship_id', sa.BigInteger(), nullable=False),
        sa.Column('trader_wallet_address', sa.String(42), nullable=False),
        sa.Column('original_tx_hash', sa.String(66), nullable=True),
        
        sa.Column('market_id', sa.String(100), nullable=False),
        sa.Column('position', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Numeric(20, 6), nullable=False),
        sa.Column('target_price', sa.Numeric(20, 10), nullable=True),
        sa.Column('max_slippage_percent', sa.Numeric(5, 2), nullable=False, server_default='1.00'),
        
        sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('scheduled_for', sa.TIMESTAMP(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['copy_relationship_id'], ['copy_relationships.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('celery_task_id'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", name='trade_queue_status_valid'),
        sa.CheckConstraint('priority >= 1 AND priority <= 10', name='trade_queue_priority_range'),
        sa.CheckConstraint('quantity > 0', name='trade_queue_quantity_positive'),
    )
    
    # Trade queue indexes
    op.create_index('idx_trade_queue_status_priority', 'trade_queue', ['status', 'priority', 'created_at'], 
                    postgresql_where=sa.text("status IN ('pending', 'processing')"))
    op.create_index('idx_trade_queue_user_id', 'trade_queue', ['user_id', sa.text('created_at DESC')])
    op.create_index('idx_trade_queue_celery_task', 'trade_queue', ['celery_task_id'], postgresql_where=sa.text('celery_task_id IS NOT NULL'))
    op.create_index('idx_trade_queue_expires_at', 'trade_queue', ['expires_at'], postgresql_where=sa.text('expires_at IS NOT NULL'))
    op.create_index('idx_trade_queue_created_at', 'trade_queue', [sa.text('created_at DESC')])
    
    # =========================================================================
    # TRIGGERS
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute('CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()')
    op.execute('CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON polymarket_api_keys FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()')
    op.execute('CREATE TRIGGER update_copy_rel_updated_at BEFORE UPDATE ON copy_relationships FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()')
    op.execute('CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()')
    
    # =========================================================================
    # VIEWS
    # =========================================================================
    op.execute("""
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
        WHERE cr.status = 'active' AND u.is_active = true
    """)
    
    op.execute("""
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
        GROUP BY u.id, u.email, u.subscription_tier, u.balance_usd
    """)


def downgrade() -> None:
    """Drop all tables and related objects"""
    
    # Drop views
    op.execute('DROP VIEW IF EXISTS v_user_portfolio')
    op.execute('DROP VIEW IF EXISTS v_active_copy_relationships')
    
    # Drop triggers
    op.execute('DROP TRIGGER IF EXISTS update_trades_updated_at ON trades')
    op.execute('DROP TRIGGER IF EXISTS update_copy_rel_updated_at ON copy_relationships')
    op.execute('DROP TRIGGER IF EXISTS update_api_keys_updated_at ON polymarket_api_keys')
    op.execute('DROP TRIGGER IF EXISTS update_users_updated_at ON users')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
    
    # Drop tables (reverse order of creation)
    op.drop_table('trade_queue')
    op.drop_table('trades')
    op.drop_table('copy_relationships')
    op.drop_table('traders')
    op.drop_table('polymarket_api_keys')
    op.drop_table('users')
    
    # Note: Extensions are not dropped as they may be used by other databases
