"""Bot accessor package with decomposed chat flow modules."""

from app.accessors.bot.admin import AdminBotMixin
from app.accessors.bot.common import CommonBotMixin
from app.accessors.bot.group import GroupBotMixin
from app.accessors.bot.single import SingleBotMixin
from app.accessors.bot.snapshot import _DEALER_REVEAL_STATES, SnapshotBotMixin


class BotGameAccessor(CommonBotMixin, SnapshotBotMixin, GroupBotMixin, SingleBotMixin, AdminBotMixin):
    """Encapsulates bot-facing chat flows that do not rely on session ids."""


__all__ = ["BotGameAccessor", "_DEALER_REVEAL_STATES"]
