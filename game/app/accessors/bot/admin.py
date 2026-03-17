"""Admin bot flows."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import Player
from app.schemas import AdminBanRequest, AdminTopupRequest


class AdminBotMixin:
    async def admin_topup(self, payload: AdminTopupRequest) -> dict:
        async for db in self._iter_db():
            player = await self._get_player_by_identifier(db, payload.username)
            if player is None:
                raise NotFoundError(f"Player '{payload.username}' not found")
            player.bank += payload.amount
            await db.commit()
            return {"username": player.username or player.telegram_id, "new_bank": player.bank}
        raise RuntimeError("Database session is unavailable")

    async def admin_ban(self, payload: AdminBanRequest) -> dict:
        async for db in self._iter_db():
            player = await self._get_player_by_identifier(db, payload.username)
            if player is None:
                raise NotFoundError(f"Player '{payload.username}' not found")
            player.is_banned = True
            await db.commit()
            return {"username": player.username or player.telegram_id, "is_banned": player.is_banned}
        raise RuntimeError("Database session is unavailable")

    async def _get_player_by_identifier(self, db: AsyncSession, identifier: str) -> Player | None:
        result = await db.execute(select(Player).where(Player.username == identifier))
        player = result.scalar_one_or_none()
        if player is not None:
            return player

        result = await db.execute(select(Player).where(Player.telegram_id == identifier))
        return result.scalar_one_or_none()
