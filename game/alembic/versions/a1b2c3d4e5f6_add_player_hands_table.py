"""add player_hands table for split foundation

Revision ID: a1b2c3d4e5f6
Revises: 9f0a1b2c3d4e
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9f0a1b2c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


participantstatus = postgresql.ENUM(
    "joined",
    "active",
    "inactive",
    "settled",
    name="participantstatus",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "player_hands",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_to_session_id", sa.Integer(), nullable=False),
        sa.Column("hand_index", sa.Integer(), nullable=False),
        sa.Column("cards", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("bet", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("participant_status", participantstatus, nullable=False, server_default="joined"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["player_to_session_id"], ["player_to_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_to_session_id", "hand_index", name="uq_player_hand_index"),
        sa.CheckConstraint("hand_index >= 0 AND hand_index <= 2", name="ck_player_hands_hand_index_range"),
    )
    op.create_index("ix_player_hands_player_to_session_id", "player_hands", ["player_to_session_id"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO player_hands (player_to_session_id, hand_index, cards, bet, participant_status, created_at)
            SELECT id, 0, cards, bet, participant_status, NOW()
            FROM player_to_session
            """
        )
    )

    op.alter_column("player_hands", "cards", server_default=None)
    op.alter_column("player_hands", "bet", server_default=None)
    op.alter_column("player_hands", "participant_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_player_hands_player_to_session_id", table_name="player_hands")
    op.drop_table("player_hands")
