"""add role to users

Revision ID: 3b7d1c9a5e42
Revises: ca940eccf1ed
Create Date: 2026-10-22 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b7d1c9a5e42'
down_revision = 'ca940eccf1ed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='user', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'role')
