"""add turn_version to game_sessions

Revision ID: 7c8d9e0f1a2b
Revises: 4b5c6d7e8f9a
Create Date: 2026-03-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c8d9e0f1a2b'
down_revision: Union[str, None] = '4b5c6d7e8f9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'game_sessions',
        sa.Column('turn_version', sa.Integer(), server_default='0', nullable=False),
    )
    op.execute("UPDATE game_sessions SET turn_version = 0 WHERE turn_version IS NULL")
    op.alter_column('game_sessions', 'turn_version', server_default=None)


def downgrade() -> None:
    op.drop_column('game_sessions', 'turn_version')
