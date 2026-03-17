"""rename active status to player_turn

Revision ID: f378b228bf45
Revises: 60d60fc1454d
Create Date: 2026-03-14 16:20:06.595030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f378b228bf45'
down_revision: Union[str, None] = '60d60fc1454d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f('uq_active_session_per_deck'),
        table_name='game_sessions',
        postgresql_where="(status = 'active'::sessionstatus)",
    )
    op.execute("ALTER TYPE sessionstatus RENAME VALUE 'active' TO 'player_turn'")
    op.create_index(
        'uq_player_turn_session_per_deck',
        'game_sessions',
        ['deck_id'],
        unique=True,
        postgresql_where=sa.text("status = 'player_turn'"),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_player_turn_session_per_deck',
        table_name='game_sessions',
        postgresql_where=sa.text("status = 'player_turn'"),
    )
    op.execute("ALTER TYPE sessionstatus RENAME VALUE 'player_turn' TO 'active'")
    op.create_index(
        op.f('uq_active_session_per_deck'),
        'game_sessions',
        ['deck_id'],
        unique=True,
        postgresql_where="(status = 'active'::sessionstatus)",
    )
