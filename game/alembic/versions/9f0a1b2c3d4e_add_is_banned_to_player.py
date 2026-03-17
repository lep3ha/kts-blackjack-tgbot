"""add is_banned to players

Revision ID: 9f0a1b2c3d4e
Revises: 8e1a2b3c4d5e
Create Date: 2026-03-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f0a1b2c3d4e'
down_revision: Union[str, None] = '8e1a2b3c4d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'players',
        sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('players', 'is_banned')
