"""add chat mode and participant status

Revision ID: 3d4a5e6f7a8b
Revises: f378b228bf45
Create Date: 2026-03-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d4a5e6f7a8b'
down_revision: Union[str, None] = 'f378b228bf45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


chat_mode_enum = sa.Enum('group', 'single', name='chatmode')
participant_status_enum = sa.Enum('joined', 'active', 'inactive', 'settled', name='participantstatus')


def upgrade() -> None:
    bind = op.get_bind()
    chat_mode_enum.create(bind, checkfirst=True)
    participant_status_enum.create(bind, checkfirst=True)

    op.add_column(
        'game_sessions',
        sa.Column('chat_mode', chat_mode_enum, nullable=True, server_default='group'),
    )
    op.add_column(
        'player_to_session',
        sa.Column('participant_status', participant_status_enum, nullable=True, server_default='joined'),
    )

    op.execute(
        """
        UPDATE player_to_session AS pts
        SET participant_status = CASE
            WHEN gs.status = 'closed' THEN 'settled'::participantstatus
            WHEN gs.status = 'player_turn' THEN 'active'::participantstatus
            ELSE 'joined'::participantstatus
        END
        FROM game_sessions AS gs
        WHERE gs.id = pts.session_id
        """
    )

    op.alter_column('game_sessions', 'chat_mode', nullable=False, server_default=None)
    op.alter_column('player_to_session', 'participant_status', nullable=False, server_default=None)

    op.create_check_constraint('ck_players_bank_non_negative', 'players', 'bank >= 0')

    op.drop_index(
        'uq_player_turn_session_per_deck',
        table_name='game_sessions',
        postgresql_where=sa.text("status = 'player_turn'"),
    )
    op.create_index(
        'uq_unfinished_session_per_deck',
        'game_sessions',
        ['deck_id'],
        unique=True,
        postgresql_where=sa.text("status != 'closed'"),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_unfinished_session_per_deck',
        table_name='game_sessions',
        postgresql_where=sa.text("status != 'closed'"),
    )
    op.create_index(
        'uq_player_turn_session_per_deck',
        'game_sessions',
        ['deck_id'],
        unique=True,
        postgresql_where=sa.text("status = 'player_turn'"),
    )

    op.drop_constraint('ck_players_bank_non_negative', 'players', type_='check')
    op.drop_column('player_to_session', 'participant_status')
    op.drop_column('game_sessions', 'chat_mode')

    bind = op.get_bind()
    participant_status_enum.drop(bind, checkfirst=True)
    chat_mode_enum.drop(bind, checkfirst=True)