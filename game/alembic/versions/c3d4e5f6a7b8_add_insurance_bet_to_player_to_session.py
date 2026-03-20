"""add insurance_bet to player_to_session

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-19 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "player_to_session",
        sa.Column("insurance_bet", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.execute("UPDATE player_to_session SET insurance_bet = 0 WHERE insurance_bet IS NULL")
    op.alter_column("player_to_session", "insurance_bet", server_default=None)


def downgrade() -> None:
    op.drop_column("player_to_session", "insurance_bet")
