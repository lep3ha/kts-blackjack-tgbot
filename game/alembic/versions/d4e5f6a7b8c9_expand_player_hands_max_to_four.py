"""expand player_hands hand index range to 0..3

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_player_hands_hand_index_range", "player_hands", type_="check")
    op.create_check_constraint(
        "ck_player_hands_hand_index_range",
        "player_hands",
        sa.text("hand_index >= 0 AND hand_index <= 3"),
    )


def downgrade() -> None:
    op.drop_constraint("ck_player_hands_hand_index_range", "player_hands", type_="check")
    op.create_check_constraint(
        "ck_player_hands_hand_index_range",
        "player_hands",
        sa.text("hand_index >= 0 AND hand_index <= 2"),
    )
