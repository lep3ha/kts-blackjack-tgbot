"""Application accessors and related app keys."""
from aiohttp import web

from app.core.config import Settings, settings

from app.accessors.blackjack_accessor import BlackjackAccessor
from app.accessors.bot_accessor import BotGameAccessor
from app.accessors.catalog_accessor import CatalogAccessor

catalog_accessor_key = web.AppKey("catalog_accessor", CatalogAccessor)
blackjack_accessor_key = web.AppKey("blackjack_accessor", BlackjackAccessor)
bot_accessor_key = web.AppKey("bot_accessor", BotGameAccessor)


def setup_accessors(app: web.Application, *, cfg: Settings | None = None) -> None:
    """Register accessor instances in aiohttp application state."""
    cfg = cfg or settings
    app[catalog_accessor_key] = CatalogAccessor()
    app[blackjack_accessor_key] = BlackjackAccessor()
    app[bot_accessor_key] = BotGameAccessor(include_legacy_fields=cfg.bot_snapshot_include_legacy_fields)
