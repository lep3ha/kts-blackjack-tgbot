"""add username and first_name to players

Revision ID: 8e1a2b3c4d5e
Revises: 7c8d9e0f1a2b
Create Date: 2026-03-16 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e1a2b3c4d5e'
down_revision: Union[str, None] = '7c8d9e0f1a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('players', sa.Column('username', sa.String(length=64), nullable=True))
    op.add_column('players', sa.Column('first_name', sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column('players', 'first_name')
    op.drop_column('players', 'username')
