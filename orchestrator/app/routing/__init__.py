"""Routing primitives for command dispatch."""

from app.routing.dispatcher import OrchestratorCommandDispatcher
from app.routing.dedup import build_dedup_key
from app.routing.game_client import GameServiceClient
from app.routing.game_client import GameServiceTransportError
from app.routing.game_client import HttpGameServiceClient
from app.routing.handlers import GameCommandHandlers
from app.routing.interfaces import CommandDispatcher
from app.routing.interfaces import UpdateNormalizer
from app.routing.models import OrchestratorCommand
from app.routing.models import OrchestratorResult
from app.routing.normalizer import TelegramUpdateNormalizer
from app.routing.pipeline import OrchestratorPipeline
from app.routing.processor import DeduplicatingCommandProcessor

__all__ = [
	"CommandDispatcher",
	"DeduplicatingCommandProcessor",
	"GameServiceClient",
	"GameServiceTransportError",
	"GameCommandHandlers",
	"HttpGameServiceClient",
	"OrchestratorCommand",
	"OrchestratorCommandDispatcher",
	"OrchestratorPipeline",
	"OrchestratorResult",
	"TelegramUpdateNormalizer",
	"UpdateNormalizer",
	"build_dedup_key",
]