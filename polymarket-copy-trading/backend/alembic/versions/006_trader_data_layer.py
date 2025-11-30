"""
Add enhanced trader data layer tables

Revision ID: 006
Revises: 004
Create Date: 2025-12-01 00:20:00.000000

This migration creates the new trader data layer tables for The Graph Protocol:
- traders_v2: Enhanced trader model with wallet_address as PK
- trader_stats: Time-series daily statistics (TimescaleDB hypertable compatible)
- trader_markets: Individual market positions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '006'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create new trader data layer tables"""
    
    # Create traders_v2 table
    op.create_table(
        'traders_v2',
        sa.Column('wallet_address', sa.String(length=42), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('total_volume', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0.0'),
        sa.Column('total_pnl', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0.0'),
        sa.Column('win_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('markets_traded', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_trade_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('wallet_address'),
        sa.CheckConstraint('win_rate >= 0 AND win_rate <= 100', name='check_win_rate_range'),
        sa.CheckConstraint('total_trades >= 0', name='check_total_trades_positive'),
        sa.CheckConstraint('markets_traded >= 0', name='check_markets_traded_positive'),
    )
    
    # Create indexes for traders_v2
    op.create_index('idx_trader_total_pnl', 'traders_v2', ['total_pnl'])
    op.create_index('idx_trader_win_rate', 'traders_v2', ['win_rate'])
    op.create_index('idx_trader_total_volume', 'traders_v2', ['total_volume'])
    op.create_index('idx_trader_performance', 'traders_v2', ['total_pnl', 'win_rate', 'total_volume'])
    op.create_index(op.f('ix_traders_v2_wallet_address'), 'traders_v2', ['wallet_address'], unique=False)
    
    # Create trader_stats table (time-series)
    op.create_table(
        'trader_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('wallet_address', sa.String(length=42), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('daily_pnl', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0.0'),
        sa.Column('daily_volume', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0.0'),
        sa.Column('trades_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('win_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('loss_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['wallet_address'], ['traders_v2.wallet_address'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('trades_count >= 0', name='check_trades_count_positive'),
        sa.CheckConstraint('win_count >= 0', name='check_win_count_positive'),
        sa.CheckConstraint('loss_count >= 0', name='check_loss_count_positive'),
        sa.CheckConstraint('win_count + loss_count <= trades_count', name='check_win_loss_sum'),
    )
    
    # Create indexes for trader_stats
    op.create_index('idx_trader_stats_wallet_date', 'trader_stats', ['wallet_address', 'date'], unique=True)
    op.create_index('idx_trader_stats_date', 'trader_stats', ['date'])
    op.create_index('idx_trader_stats_pnl', 'trader_stats', ['daily_pnl'])
    op.create_index(op.f('ix_trader_stats_wallet_address'), 'trader_stats', ['wallet_address'], unique=False)
    
    # Create trader_markets table
    op.create_table(
        'trader_markets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('wallet_address', sa.String(length=42), nullable=False),
        sa.Column('market_id', sa.String(length=100), nullable=False),
        sa.Column('market_name', sa.String(length=500), nullable=True),
        sa.Column('position_side', sa.Enum('YES', 'NO', name='positionside'), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'CLOSED', name='positionstatus'), nullable=False, server_default='OPEN'),
        sa.Column('pnl', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['wallet_address'], ['traders_v2.wallet_address'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('entry_price > 0', name='check_entry_price_positive'),
        sa.CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )
    
    # Create indexes for trader_markets
    op.create_index('idx_trader_market_wallet', 'trader_markets', ['wallet_address', 'market_id'])
    op.create_index('idx_trader_market_status', 'trader_markets', ['status'])
    op.create_index('idx_trader_market_pnl', 'trader_markets', ['pnl'])
    op.create_index(op.f('ix_trader_markets_wallet_address'), 'trader_markets', ['wallet_address'], unique=False)
    op.create_index(op.f('ix_trader_markets_market_id'), 'trader_markets', ['market_id'], unique=False)


def downgrade() -> None:
    """Drop trader data layer tables"""
    
    # Drop indexes first
    op.drop_index(op.f('ix_trader_markets_market_id'), table_name='trader_markets')
    op.drop_index(op.f('ix_trader_markets_wallet_address'), table_name='trader_markets')
    op.drop_index('idx_trader_market_pnl', table_name='trader_markets')
    op.drop_index('idx_trader_market_status', table_name='trader_markets')
    op.drop_index('idx_trader_market_wallet', table_name='trader_markets')
    
    op.drop_index(op.f('ix_trader_stats_wallet_address'), table_name='trader_stats')
    op.drop_index('idx_trader_stats_pnl', table_name='trader_stats')
    op.drop_index('idx_trader_stats_date', table_name='trader_stats')
    op.drop_index('idx_trader_stats_wallet_date', table_name='trader_stats')
    
    op.drop_index(op.f('ix_traders_v2_wallet_address'), table_name='traders_v2')
    op.drop_index('idx_trader_performance', table_name='traders_v2')
    op.drop_index('idx_trader_total_volume', table_name='traders_v2')
    op.drop_index('idx_trader_win_rate', table_name='traders_v2')
    op.drop_index('idx_trader_total_pnl', table_name='traders_v2')
    
    # Drop tables
    op.drop_table('trader_markets')
    op.drop_table('trader_stats')
    op.drop_table('traders_v2')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS positionstatus')
    op.execute('DROP TYPE IF EXISTS positionside')
