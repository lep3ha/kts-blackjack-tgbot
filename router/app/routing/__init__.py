"""Routing primitives for command dispatch."""

from app.routing.dispatcher import RouterCommandDispatcher
from app.routing.dedup import build_dedup_key
from app.routing.handlers import GameCommandHandlers
from app.routing.interfaces import CommandDispatcher
from app.routing.interfaces import UpdateNormalizer
from app.routing.models import RouterCommand
from app.routing.models import RouterResult
from app.routing.normalizer import TelegramUpdateNormalizer
from app.routing.pipeline import RouterPipeline
from app.routing.processor import DeduplicatingCommandProcessor

__all__ = [
	"CommandDispatcher",
	"DeduplicatingCommandProcessor",
	"GameCommandHandlers",
	"RouterCommand",
	"RouterCommandDispatcher",
	"RouterPipeline",
	"RouterResult",
	"TelegramUpdateNormalizer",
	"UpdateNormalizer",
	"build_dedup_key",
]