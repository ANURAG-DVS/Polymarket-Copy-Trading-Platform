"""Add trader, trade, and copy_relationship tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('subscription_tier', sa.Enum('free', 'pro', 'enterprise', name='subscriptiontier'), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('telegram_id', sa.Integer(), nullable=True),
        sa.Column('polymarket_api_key', sa.String(), nullable=True),
        sa.Column('polymarket_api_secret', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reset_token', sa.String(), nullable=True),
        sa.Column('reset_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)

    # Create traders table
    op.create_table(
        'traders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wallet_address', sa.String(), nullable=False),
        sa.Column('total_pnl', sa.Float(), nullable=True, default=0.0),
        sa.Column('pnl_7d', sa.Float(), nullable=True, default=0.0),
        sa.Column('pnl_30d', sa.Float(), nullable=True, default=0.0),
        sa.Column('pnl_all_time', sa.Float(), nullable=True, default=0.0),
        sa.Column('win_rate', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_trades', sa.Integer(), nullable=True, default=0),
        sa.Column('winning_trades', sa.Integer(), nullable=True, default=0),
        sa.Column('losing_trades', sa.Integer(), nullable=True, default=0),
        sa.Column('avg_trade_size', sa.Float(), nullable=True, default=0.0),
        sa.Column('max_trade_size', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_volume', sa.Float(), nullable=True, default=0.0),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True, default=0.0),
        sa.Column('max_drawdown', sa.Float(), nullable=True, default=0.0),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('rank_7d', sa.Integer(), nullable=True),
        sa.Column('rank_30d', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_trade_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_traders_wallet_address'), 'traders', ['wallet_address'], unique=True)
    op.create_index(op.f('ix_traders_rank'), 'traders', ['rank'], unique=False)

    # Create trades table
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trader_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('market_id', sa.String(), nullable=False),
        sa.Column('market_title', sa.String(), nullable=False),
        sa.Column('outcome', sa.String(), nullable=False),
        sa.Column('side', sa.Enum('yes', 'no', name='tradeside'), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('amount_usd', sa.Float(), nullable=False),
        sa.Column('realized_pnl', sa.Float(), nullable=True, default=0.0),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True, default=0.0),
        sa.Column('status', sa.Enum('open', 'closed', 'cancelled', name='tradestatus'), nullable=True),
        sa.Column('polymarket_order_id', sa.String(), nullable=True),
        sa.Column('blockchain_tx_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['trader_id'], ['traders.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trades_trader_id'), 'trades', ['trader_id'], unique=False)
    op.create_index(op.f('ix_trades_user_id'), 'trades', ['user_id'], unique=False)
    op.create_index(op.f('ix_trades_market_id'), 'trades', ['market_id'], unique=False)
    op.create_index(op.f('ix_trades_status'), 'trades', ['status'], unique=False)
    op.create_index(op.f('ix_trades_created_at'), 'trades', ['created_at'], unique=False)

    # Create copy_relationships table
    op.create_table(
        'copy_relationships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('trader_id', sa.Integer(), nullable=False),
        sa.Column('copy_percentage', sa.Float(), nullable=False),
        sa.Column('max_investment_usd', sa.Float(), nullable=False),
        sa.Column('total_pnl', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_trades_copied', sa.Integer(), nullable=True, default=0),
        sa.Column('status', sa.Enum('active', 'paused', 'stopped', name='relationshipstatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['trader_id'], ['traders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_copy_relationships_user_id'), 'copy_relationships', ['user_id'], unique=False)
    op.create_index(op.f('ix_copy_relationships_trader_id'), 'copy_relationships', ['trader_id'], unique=False)
    op.create_index(op.f('ix_copy_relationships_status'), 'copy_relationships', ['status'], unique=False)

def downgrade() -> None:
    op.drop_table('copy_relationships')
    op.drop_table('trades')
    op.drop_table('traders')
    op.drop_table('users')
    op.execute('DROP TYPE tradestatus')
    op.execute('DROP TYPE tradeside')
    op.execute('DROP TYPE relationshipstatus')
    op.execute('DROP TYPE subscriptiontier')
