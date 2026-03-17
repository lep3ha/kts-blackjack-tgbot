from .admin import AdminCommandHandlers
from .session import SessionCommandHandlers


class GameCommandHandlers(SessionCommandHandlers, AdminCommandHandlers):
    """Facade class that combines all routing command handler groups."""

    pass
