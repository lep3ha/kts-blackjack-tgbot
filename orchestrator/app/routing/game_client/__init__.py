"""Game service client abstractions and contracts."""

from app.routing.game_client.client import GameServiceTransportError
from app.routing.game_client.client import HttpGameServiceClient
from app.routing.game_client.interfaces import GameServiceClient
from app.routing.game_client.models import CurrentSessionRequest
from app.routing.game_client.models import AdminBanRequest
from app.routing.game_client.models import AdminTopupRequest
from app.routing.game_client.models import GameErrorCode
from app.routing.game_client.models import GameServiceEnvelope
from app.routing.game_client.models import GameServiceError
from app.routing.game_client.models import GroupJoinRequest
from app.routing.game_client.models import GroupOpenRequest
from app.routing.game_client.models import GroupStartRequest
from app.routing.game_client.models import PlayerActionRequest
from app.routing.game_client.models import RegisterPlayerRequest
from app.routing.game_client.models import SingleStartRequest
from app.routing.game_client.models import SingleStopRequest
from app.routing.game_client.models import TimeoutTurnRequest

__all__ = [
	"GameErrorCode",
	"GameServiceClient",
	"GameServiceEnvelope",
	"GameServiceError",
	"GameServiceTransportError",
	"CurrentSessionRequest",
	"AdminBanRequest",
	"AdminTopupRequest",
	"GroupJoinRequest",
	"GroupOpenRequest",
	"GroupStartRequest",
	"HttpGameServiceClient",
	"PlayerActionRequest",
	"RegisterPlayerRequest",
	"SingleStartRequest",
	"SingleStopRequest",
	"TimeoutTurnRequest",
]