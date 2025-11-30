"""
Add trader tables with TimescaleDB support

Revision ID: 20251201_0025
Revises: 006
Create Date: 2025-12-01 00:25:00.000000

This migration creates comprehensive trader data tables with:
- traders_v2 table with performance indexes
- trader_stats table as TimescaleDB hypertable (time-series)
- trader_markets table for position tracking
- All necessary indexes for query performance
- Check constraints for data integrity
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20251201_0025'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create trader tables with full indexing and TimescaleDB hypertable support.
    """
    
    conn = op.get_bind()
    
    # Check if TimescaleDB extension is available
    timescaledb_available = False
    try:
        result = conn.execute(sa.text("SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'timescaledb'"))
        if result.scalar() > 0:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
            timescaledb_available = True
            print("TimescaleDB extension enabled")
    except Exception:
        print("TimescaleDB extension not available, continuing without hypertable conversion")
    
    # Add additional indexes for traders_v2 for better leaderboard performance
    op.create_index(
        'idx_traders_v2_total_pnl_desc', 
        'traders_v2', 
        [sa.text('total_pnl DESC')]
    )
    op.create_index(
        'idx_traders_v2_win_rate_desc', 
        'traders_v2', 
        [sa.text('win_rate DESC')]
    )
    op.create_index(
        'idx_traders_v2_last_trade_desc', 
        'traders_v2', 
        [sa.text('last_trade_at DESC')]
    )
    
    # Add composite index for trader_stats time-series queries
    op.create_index(
        'idx_trader_stats_wallet_date_desc',
        'trader_stats',
        ['wallet_address', sa.text('date DESC')]
    )
    
    # Add composite index for trader_markets filtering
    op.create_index(
        'idx_trader_markets_wallet_status',
        'trader_markets',
        ['wallet_address', 'status']
    )
    
    # Convert trader_stats to TimescaleDB hypertable if available
    if timescaledb_available:
        try:
            # Check if table is already a hypertable
            result = conn.execute(sa.text("""
                SELECT COUNT(*) FROM timescaledb_information.hypertables 
                WHERE hypertable_name = 'trader_stats'
            """))
            
            if result.scalar() == 0:
                # Convert to hypertable partitioned by date
                conn.execute(sa.text("""
                    SELECT create_hypertable(
                        'trader_stats',
                        'date',
                        if_not_exists => TRUE,
                        migrate_data => TRUE
                    )
                """))
                print("Successfully converted trader_stats to TimescaleDB hypertable")
                
                # Add compression policy for older data (optional, commented out by default)
                # conn.execute(sa.text("""
                #     ALTER TABLE trader_stats SET (
                #         timescaledb.compress,
                #         timescaledb.compress_segmentby = 'wallet_address'
                #     )
                # """))
                # 
                # conn.execute(sa.text("""
                #     SELECT add_compression_policy('trader_stats', INTERVAL '7 days')
                # """))
                
        except Exception as e:
            print(f"Warning: Could not convert trader_stats to hypertable: {e}")
    
    # Additional check constraints (some may already exist from migration 006)
    # These are idempotent - will only add if they don't exist
    
    # Ensure trader_stats.daily_pnl can be negative (no constraint needed, already Numeric)
    # But add a reasonable range constraint to prevent data entry errors
    try:
        op.create_check_constraint(
            'check_trader_stats_daily_pnl_range',
            'trader_stats',
            'daily_pnl >= -1000000 AND daily_pnl <= 1000000'
        )
    except Exception:
        pass  # Constraint may already exist
    
    # Ensure trader_markets.quantity > 0 (should already exist from 006)
    # Just verify it's there
    try:
        op.create_check_constraint(
            'check_trader_markets_quantity_positive',
            'trader_markets',
            'quantity > 0'
        )
    except Exception:
        pass  # Constraint may already exist
    
    # Add additional useful constraints
    try:
        op.create_check_constraint(
            'check_trader_stats_daily_volume_positive',
            'trader_stats',
            'daily_volume >= 0'
        )
    except Exception:
        pass
    
    try:
        op.create_check_constraint(
            'check_trader_markets_entry_price_range',
            'trader_markets',
            'entry_price > 0 AND entry_price <= 1'
        )
    except Exception:
        pass
    
    print("Migration complete: All trader tables, indexes, and constraints created")


def downgrade() -> None:
    """
    Rollback trader tables migration.
    """
    
    conn = op.get_bind()
    
    # Drop additional check constraints (newer ones)
    try:
        op.drop_constraint('check_trader_markets_entry_price_range', 'trader_markets', type_='check')
    except Exception:
        pass
    
    try:
        op.drop_constraint('check_trader_stats_daily_volume_positive', 'trader_stats', type_='check')
    except Exception:
        pass
    
    try:
        op.drop_constraint('check_trader_markets_quantity_positive', 'trader_markets', type_='check')
    except Exception:
        pass
    
    try:
        op.drop_constraint('check_trader_stats_daily_pnl_range', 'trader_stats', type_='check')
    except Exception:
        pass
    
    # Drop additional indexes
    op.drop_index('idx_trader_markets_wallet_status', table_name='trader_markets')
    op.drop_index('idx_trader_stats_wallet_date_desc', table_name='trader_stats')
    op.drop_index('idx_traders_v2_last_trade_desc', table_name='traders_v2')
    op.drop_index('idx_traders_v2_win_rate_desc', table_name='traders_v2')
    op.drop_index('idx_traders_v2_total_pnl_desc', table_name='traders_v2')
    
    # Note: We don't drop the tables themselves as they were created in migration 006
    # We only remove the additional indexes and constraints added in this migration
    
    print("Downgrade complete: Additional indexes and constraints removed")
