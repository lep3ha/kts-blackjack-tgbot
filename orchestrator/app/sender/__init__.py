"""Telegram sender interfaces and UI contracts."""

from app.sender.client import TelegramSenderClient
from app.sender.client import TelegramSenderError
from app.sender.interfaces import SenderService
from app.sender.models import OutboundMessage
from app.sender.models import UiButton
from app.sender.models import UiKeyboard
from app.sender.presenter import present_orchestrator_result
from app.sender.renderers import render_keyboard_markup

__all__ = [
    "OutboundMessage",
    "SenderService",
    "TelegramSenderClient",
    "TelegramSenderError",
    "UiButton",
    "UiKeyboard",
    "present_orchestrator_result",
    "render_keyboard_markup",
]