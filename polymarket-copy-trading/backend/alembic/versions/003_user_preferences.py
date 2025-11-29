"""Add user preferences and billing history

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('default_copy_percentage', sa.Float(), nullable=True, default=5.0),
        sa.Column('daily_spend_limit_usd', sa.Float(), nullable=True, default=100.0),
        sa.Column('weekly_spend_limit_usd', sa.Float(), nullable=True, default=500.0),
        sa.Column('slippage_tolerance', sa.Float(), nullable=True, default=1.0),
        sa.Column('auto_stop_loss_percentage', sa.Float(), nullable=True),
        sa.Column('auto_take_profit_percentage', sa.Float(), nullable=True),
        sa.Column('email_trade_execution', sa.Boolean(), nullable=True, default=True),
        sa.Column('email_daily_summary', sa.Boolean(), nullable=True, default=False),
        sa.Column('email_security_alerts', sa.Boolean(), nullable=True, default=True),
        sa.Column('telegram_trade_execution', sa.Boolean(), nullable=True, default=False),
        sa.Column('telegram_daily_summary', sa.Boolean(), nullable=True, default=False),
        sa.Column('telegram_security_alerts', sa.Boolean(), nullable=True, default=True),
        sa.Column('notification_frequency', sa.String(), nullable=True, default='instant'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=True)

    # Create billing_history table
    op.create_table(
        'billing_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True, default='USD'),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_history_user_id'), 'billing_history', ['user_id'], unique=False)

def downgrade() -> None:
    op.drop_table('billing_history')
    op.drop_table('user_preferences')
