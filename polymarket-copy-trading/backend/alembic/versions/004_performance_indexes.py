"""
Database performance optimization indexes
Add these via migration
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    """Add performance indexes"""
    
    # Traders table - Leaderboard queries
    op.create_index(
        'idx_traders_leaderboard',
        'traders',
        ['pnl_7d', 'win_rate', 'total_trades'],
        postgresql_where=sa.text('is_active = true')
    )
    
    # Traders - Ranking queries
    op.create_index(
        'idx_traders_ranking',
        'traders',
        ['rank_7d', 'rank_30d'],
        postgresql_where=sa.text('is_active = true')
    )
    
    # Trades - User trades lookup
    op.create_index(
        'idx_trades_user_status',
        'trades',
        ['user_id', 'status', 'created_at'],
    )
    
    # Trades - Trader trades lookup
    op.create_index(
        'idx_trades_trader_status',
        'trades',
        ['trader_id', 'status', 'created_at'],
    )
    
    # Trades - P&L calculation
    op.create_index(
        'idx_trades_pnl',
        'trades',
        ['user_id', 'trader_id', 'status'],
        postgresql_include=['realized_pnl', 'unrealized_pnl']
    )
    
    # Copy relationships - Active relationships
    op.create_index(
        'idx_copy_relationships_active',
        'copy_relationships',
        ['user_id', 'trader_id', 'status'],
        postgresql_where=sa.text("status = 'active'")
    )
    
    # Notifications - Unread lookup
    op.create_index(
        'idx_notifications_unread',
        'notifications',
        ['user_id', 'created_at'],
        postgresql_where=sa.text('is_read = false')
    )
    
    # User balances - Quick lookup
    op.create_index(
        'idx_user_balances_user',
        'user_balances',
        ['user_id', 'updated_at']
    )
    
    # Compound index for dashboard queries
    op.create_index(
        'idx_trades_dashboard',
        'trades',
        ['user_id', 'status', 'created_at'],
        postgresql_include=['amount_usd', 'realized_pnl', 'unrealized_pnl']
    )

def downgrade():
    """Remove performance indexes"""
    op.drop_index('idx_traders_leaderboard')
    op.drop_index('idx_traders_ranking')
    op.drop_index('idx_trades_user_status')
    op.drop_index('idx_trades_trader_status')
    op.drop_index('idx_trades_pnl')
    op.drop_index('idx_copy_relationships_active')
    op.drop_index('idx_notifications_unread')
    op.drop_index('idx_user_balances_user')
    op.drop_index('idx_trades_dashboard')
