"""
Add Stripe fields to User model

Revision ID: 005
Revises: 004
Create Date: 2024-01-01 00:05:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade():
    """Add Stripe-related fields to users table"""
    
    # Add Stripe customer ID
    op.add_column('users', sa.Column(
        'stripe_customer_id',
        sa.String(255),
        nullable=True,
        unique=True
    ))
    
    # Add Stripe subscription ID
    op.add_column('users', sa.Column(
        'stripe_subscription_id',
        sa.String(255),
        nullable=True
    ))
    
    # Add subscription status
    op.add_column('users', sa.Column(
        'subscription_status',
        sa.String(50),
        nullable=True,
        server_default='active'
    ))
    
    # Add index on stripe_customer_id for faster lookups
    op.create_index(
        'idx_users_stripe_customer',
        'users',
        ['stripe_customer_id']
    )

def downgrade():
    """Remove Stripe-related fields"""
    
    op.drop_index('idx_users_stripe_customer')
    op.drop_column('users', 'subscription_status')
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
