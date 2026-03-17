"""expand session status lifecycle

Revision ID: 4b5c6d7e8f9a
Revises: 3d4a5e6f7a8b
Create Date: 2026-03-15 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4b5c6d7e8f9a'
down_revision: Union[str, None] = '3d4a5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE sessionstatus RENAME VALUE 'waiting_for_players' TO 'lobby_open'")
    op.execute("ALTER TYPE sessionstatus RENAME VALUE 'player_turn' TO 'in_progress'")
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'stopped'")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported because PostgreSQL enum value removal is unsafe for this lifecycle migration"
    )