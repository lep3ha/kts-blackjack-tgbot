import logging
from datetime import datetime
from datetime import timezone

from app.routing.interfaces import UpdateNormalizer
from app.routing.models import RouterCommand
from app.routing.models import RouterResult
from app.routing.processor import DeduplicatingCommandProcessor
from app.sender import SenderService
from app.sender.presenter import present_router_result
from app.state.interfaces import SessionContextStore
from app.state.models import SessionContext
from app.timers.interfaces import TimerScheduler
from app.upstream.contracts import TelegramUpdateEnvelope


logger = logging.getLogger(__name__)


class RouterPipeline:
    def __init__(
        self,
        *,
        normalizer: UpdateNormalizer,
        processor: DeduplicatingCommandProcessor,
        sender: SenderService,
        timer_scheduler: TimerScheduler,
        session_context_store: SessionContextStore | None = None,
        context_ttl_seconds: int = 7200,
    ) -> None:
        self._normalizer = normalizer
        self._processor = processor
        self._sender = sender
        self._timer_scheduler = timer_scheduler
        self._session_context_store = session_context_store
        self._context_ttl_seconds = context_ttl_seconds

    async def process_envelope(self, envelope: TelegramUpdateEnvelope) -> None:
        context = await self._load_context_for_normalization(envelope)
        command = self._normalizer.normalize(envelope, context=context)
        if command.command_type == "unsupported":
            logger.info("Unsupported command skipped update_id=%s", command.update_id)
            return

        result = await self._processor.process(command)
        if result.error_code == "duplicate_skipped":
            logger.info("Duplicate command skipped update_id=%s", command.update_id)
            return

        await self._cancel_timeout_if_needed(command=command, result=result, context=context)

        await self._delete_previous_message_if_needed(command=command, result=result)

        outbound = present_router_result(command.chat_id, result)
        message_id = await self._sender.send_text(
            chat_id=outbound.chat_id,
            text=outbound.text,
            keyboard=outbound.keyboard,
        )

        if message_id is not None:
            await self._save_message_id(
                command=command,
                result=result,
                message_id=message_id,
            )

        await self._schedule_timeout_if_needed(command=command, result=result)

    async def _delete_previous_message_if_needed(
        self,
        *,
        command: RouterCommand,
        result: RouterResult,
    ) -> None:
        if command.command_type != "player_action" or not result.success:
            return

        if self._session_context_store is None:
            return

        try:
            context = await self._session_context_store.get(command.chat_id)
            if context is None or context.last_bot_message_id is None:
                return

            # Delete previous game-state message only for the current player's successful move.
            if context.current_player_telegram_id is not None and command.actor_telegram_id != context.current_player_telegram_id:
                return

            await self._sender.delete_message(
                chat_id=command.chat_id,
                message_id=context.last_bot_message_id,
            )
        except Exception:
            logger.debug("Failed to delete previous message chat_id=%s", command.chat_id)

    async def _load_context_for_normalization(self, envelope: TelegramUpdateEnvelope) -> SessionContext | None:
        if self._session_context_store is None:
            return None

        try:
            chat_id = self._extract_chat_id(envelope)
            if chat_id is None:
                return None
            return await self._session_context_store.get(chat_id)
        except Exception:
            logger.debug("Failed to load context for normalization update_id=%s", envelope.update_id)
            return None

    async def _save_message_id(
        self,
        *,
        command: RouterCommand,
        result: RouterResult,
        message_id: int,
    ) -> None:
        if self._session_context_store is None:
            return
        try:
            context = await self._session_context_store.get(command.chat_id)
            if context is None:
                context = SessionContext(chat_id=command.chat_id, chat_type=command.chat_type)
            context.last_bot_message_id = message_id
            context.reply_action_hint = self._resolve_reply_action_hint(command=command, result=result)
            await self._session_context_store.set(command.chat_id, context, self._context_ttl_seconds)
        except Exception:
            logger.debug("Failed to save message_id chat_id=%s", command.chat_id)

    @staticmethod
    def _resolve_reply_action_hint(
        *,
        command: RouterCommand,
        result: RouterResult,
    ) -> str | None:
        if command.command_type == "tutorial":
            return "group_open" if command.chat_type == "group" else "single_start"

        if command.chat_type == "single":
            return "single_start"

        if not isinstance(result.data, dict):
            return None

        session_status = result.data.get("session_status")
        if session_status == "lobby_open":
            return "group_start"
        if session_status == "closed":
            return "group_open"
        return None

    @staticmethod
    def _extract_chat_id(envelope: TelegramUpdateEnvelope) -> str | None:
        payload = envelope.payload
        message = payload.get("message")
        if isinstance(message, dict):
            chat = message.get("chat")
            if isinstance(chat, dict):
                chat_id = chat.get("id")
                if chat_id is not None:
                    return str(chat_id)

        callback_query = payload.get("callback_query")
        if isinstance(callback_query, dict):
            callback_message = callback_query.get("message")
            if isinstance(callback_message, dict):
                chat = callback_message.get("chat")
                if isinstance(chat, dict):
                    chat_id = chat.get("id")
                    if chat_id is not None:
                        return str(chat_id)

        return None

    async def _schedule_timeout_if_needed(
        self,
        *,
        command: RouterCommand,
        result: RouterResult,
    ) -> None:
        if not isinstance(result.data, dict):
            return

        current_timer = result.data.get("current_timer")
        session_id = result.data.get("session_id")
        turn_version = result.data.get("turn_version")
        if current_timer is None:
            return
        if not isinstance(session_id, int) or not isinstance(turn_version, int):
            return

        due_at = _parse_due_at(str(current_timer))
        if due_at is None:
            return

        chat_type_raw = result.data.get("chat_mode")
        chat_type = str(chat_type_raw) if chat_type_raw in {"group", "single"} else command.chat_type
        await self._timer_scheduler.schedule_timeout(
            chat_id=command.chat_id,
            chat_type=chat_type,
            session_id=session_id,
            turn_version=turn_version,
            due_at=due_at,
        )

    async def _cancel_timeout_if_needed(
        self,
        *,
        command: RouterCommand,
        result: RouterResult,
        context: SessionContext | None,
    ) -> None:
        if command.command_type != "player_action" or not result.success:
            return

        if command.turn_version is None:
            return

        if context is None or context.session_id is None:
            return

        if context.current_player_telegram_id is None:
            return

        if command.actor_telegram_id != context.current_player_telegram_id:
            return

        try:
            await self._timer_scheduler.cancel_timeout(
                chat_id=command.chat_id,
                session_id=context.session_id,
                turn_version=command.turn_version,
            )
        except Exception:
            logger.debug(
                "Failed to cancel timeout chat_id=%s session_id=%s turn_version=%s",
                command.chat_id,
                context.session_id,
                command.turn_version,
            )


def _parse_due_at(value: str) -> datetime | None:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
