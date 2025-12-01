"""merge migration heads

Revision ID: merge_heads_001
Revises: 005, 20251201_0025
Create Date: 2025-12-01 17:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads_001'
down_revision = ('005', '20251201_0025')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration - no changes needed
    pass


def downgrade() -> None:
    # Merge migration - no changes needed
    pass
