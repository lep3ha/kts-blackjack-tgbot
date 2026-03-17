"""Blackjack API route registry composed from dedicated view modules."""
from __future__ import annotations

from aiohttp import web

from app.api.views.admin import AdminBanView, AdminTopupView
from app.api.views.bot import (
    BOT_SNAPSHOT_RESPONSE_MODEL,
    BotActionView,
    BotCurrentSessionView,
    BotLastSessionView,
    BotTimeoutView,
    GroupLobbyJoinView,
    GroupLobbyOpenView,
    GroupLobbyStartView,
    GroupLobbyStateView,
    GroupPlayerStopView,
    SingleSessionStartView,
    SingleSessionStopView,
)
from app.api.views.catalog import DecksView, PlayersView, SessionPlayersView, SessionsView
from app.api.views.game import SessionActionsView, SessionStartView, SessionStateView, SessionTimeoutView


BLACKJACK_VIEW_ROUTES: list[tuple[str, type[web.View]]] = [
    ("/players", PlayersView),
    ("/decks", DecksView),
    ("/sessions", SessionsView),
    ("/sessions/{session_id}/players", SessionPlayersView),
    ("/sessions/{session_id}/start", SessionStartView),
    ("/sessions/{session_id}/actions", SessionActionsView),
    ("/sessions/{session_id}/timeout", SessionTimeoutView),
    ("/sessions/{session_id}", SessionStateView),
    ("/bot/sessions/group/open", GroupLobbyOpenView),
    ("/bot/sessions/group/join", GroupLobbyJoinView),
    ("/bot/sessions/group/lobby", GroupLobbyStateView),
    ("/bot/sessions/group/start", GroupLobbyStartView),
    ("/bot/sessions/group/player-stop", GroupPlayerStopView),
    ("/bot/sessions/single/start", SingleSessionStartView),
    ("/bot/sessions/single/stop", SingleSessionStopView),
    ("/bot/sessions/current", BotCurrentSessionView),
    ("/bot/sessions/last", BotLastSessionView),
    ("/bot/sessions/action", BotActionView),
    ("/bot/sessions/timeout", BotTimeoutView),
    ("/admin/topup", AdminTopupView),
    ("/admin/ban", AdminBanView),
]


def setup_blackjack_routes(app: web.Application) -> None:
    app.router.add_routes([web.view(path, view) for path, view in BLACKJACK_VIEW_ROUTES])


__all__ = [
    "AdminBanView",
    "AdminTopupView",
    "BLACKJACK_VIEW_ROUTES",
    "BOT_SNAPSHOT_RESPONSE_MODEL",
    "BotActionView",
    "BotCurrentSessionView",
    "BotLastSessionView",
    "BotTimeoutView",
    "DecksView",
    "GroupLobbyJoinView",
    "GroupLobbyOpenView",
    "GroupLobbyStartView",
    "GroupLobbyStateView",
    "GroupPlayerStopView",
    "PlayersView",
    "SessionActionsView",
    "SessionPlayersView",
    "SessionStartView",
    "SessionStateView",
    "SessionsView",
    "SessionTimeoutView",
    "SingleSessionStartView",
    "SingleSessionStopView",
    "setup_blackjack_routes",
]
