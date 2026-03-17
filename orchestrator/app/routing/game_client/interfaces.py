from typing import Protocol

from app.routing.game_client.models import (
    AdminBanRequest,
    AdminTopupRequest,
    CurrentSessionRequest,
    GameServiceEnvelope,
    GroupJoinRequest,
    GroupOpenRequest,
    GroupPlayerStopRequest,
    GroupStartRequest,
    PlayerActionRequest,
    RegisterPlayerRequest,
    SingleStartRequest,
    SingleStopRequest,
    TimeoutTurnRequest,
)


class GameServiceClient(Protocol):
    async def group_open(self, request: GroupOpenRequest) -> GameServiceEnvelope:
        """Open a group lobby via game-service."""

    async def group_start(self, request: GroupStartRequest) -> GameServiceEnvelope:
        """Start a group session via game-service."""

    async def group_join(self, request: GroupJoinRequest) -> GameServiceEnvelope:
        """Join a group session via game-service."""

    async def group_player_stop(self, request: GroupPlayerStopRequest) -> GameServiceEnvelope:
        """Stop the current group player while keeping the session alive when possible."""

    async def single_start(self, request: SingleStartRequest) -> GameServiceEnvelope:
        """Start a single session via game-service."""

    async def single_stop(self, request: SingleStopRequest) -> GameServiceEnvelope:
        """Stop a single session via game-service."""

    async def register_player(self, request: RegisterPlayerRequest) -> GameServiceEnvelope:
        """Register a player in game-service catalog."""

    async def player_action(self, request: PlayerActionRequest) -> GameServiceEnvelope:
        """Submit a player action via game-service."""

    async def timeout_turn(self, request: TimeoutTurnRequest) -> GameServiceEnvelope:
        """Submit a timeout action via game-service."""

    async def current_session(self, request: CurrentSessionRequest) -> GameServiceEnvelope:
        """Read current session snapshot via game-service."""

    async def admin_topup(self, request: AdminTopupRequest) -> GameServiceEnvelope:
        """Add bank amount to a player by username."""

    async def admin_ban(self, request: AdminBanRequest) -> GameServiceEnvelope:
        """Ban a player by username."""
