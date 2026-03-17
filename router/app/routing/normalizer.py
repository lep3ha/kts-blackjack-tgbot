import re
from typing import Any

from app.routing.models import CommandType
from app.routing.models import RouterCommand
from app.state.models import SessionContext
from app.upstream.contracts import TelegramUpdateEnvelope


class TelegramUpdateNormalizer:
    _JOIN_REPLY_PATTERN = re.compile(r"^Присоединиться\s*\((\d+)\)$")

    _TEXT_TO_COMMAND: dict[str, tuple[CommandType, str | None]] = {
        "/start": ("tutorial", None),
        "/single_start": ("single_start", None),
        "/create_lobby": ("group_open", None),
        "/group_start": ("group_start", None),
        "/start_round": ("group_start", None),
        "/join": ("group_join", None),
        "/register": ("player_register", None),
        "/current": ("current_session", None),
        "/admin_topup": ("admin_topup", None),
        "/admin_ban": ("admin_ban", None),
        "/hit": ("player_action", "hit"),
        "/stand": ("player_action", "stand"),
        "/double": ("player_action", "double"),
    }

    # Russian reply-keyboard labels → same command/action mapping.
    # Keys must exactly match the `action` strings used in _build_*_keyboard().
    _RU_TEXT_TO_COMMAND: dict[str, tuple[CommandType, str | None]] = {
        "Ещё": ("player_action", "hit"),
        "Стоп": ("player_action", "stand"),
        "Двойная": ("player_action", "double"),
        "Текущая": ("current_session", None),
        "Hit": ("player_action", "hit"),
        "Stand": ("player_action", "stand"),
        "Double": ("player_action", "double"),
        "Выйти из раунда": ("group_stop", None),
        "Остановить игру": ("single_stop", None),
    }

    _CALLBACK_TO_COMMAND: dict[str, tuple[CommandType, str | None]] = {
        "action:hit": ("player_action", "hit"),
        "action:stand": ("player_action", "stand"),
        "action:double": ("player_action", "double"),
        "session:current": ("current_session", None),
    }

    def normalize(
        self,
        envelope: TelegramUpdateEnvelope,
        *,
        context: SessionContext | None = None,
    ) -> RouterCommand:
        payload = envelope.payload

        if envelope.update_type == "message":
            return self._from_message(envelope, payload, context=context)

        if envelope.update_type == "callback_query":
            return self._from_callback_query(envelope, payload)

        return self._unsupported(
            envelope=envelope,
            chat_id=self._extract_chat_id(payload) or envelope.source_key,
            chat_type=self._extract_chat_type(payload),
            actor_telegram_id=self._extract_actor_id(payload),
            actor_username=self._extract_actor_username(payload),
            actor_first_name=self._extract_actor_first_name(payload),
        )

    def _from_message(
        self,
        envelope: TelegramUpdateEnvelope,
        payload: dict[str, Any],
        *,
        context: SessionContext | None,
    ) -> RouterCommand:
        message = payload.get("message")
        if not isinstance(message, dict):
            return self._unsupported(
                envelope=envelope,
                chat_id=self._extract_chat_id(payload) or envelope.source_key,
                chat_type=self._extract_chat_type(payload),
                actor_telegram_id=self._extract_actor_id(payload),
                actor_username=self._extract_actor_username(payload),
                actor_first_name=self._extract_actor_first_name(payload),
            )

        text = message.get("text")
        normalized_text = text.strip() if isinstance(text, str) else ""
        raw_command_key = normalized_text.split(" ")[0] if isinstance(text, str) else ""
        command_key = self._normalize_command_key(raw_command_key)
        bet = self._extract_bet_from_text(text)

        command_meta = self._TEXT_TO_COMMAND.get(command_key)

        if command_meta is None and command_key == "/stop":
            command_meta = self._resolve_stop_command(payload)

        if command_key in {"/create_lobby", "/group_start", "/start_round"} and command_meta is not None:
            if self._extract_chat_type(payload) != "group":
                command_meta = None

        if command_meta is None and normalized_text == "Начать игру":
            command_meta = self._resolve_start_game_command(payload, context=context)

        if command_meta is None and normalized_text in {"Закончить", "Остановить игру"}:
            command_meta = self._resolve_stop_command(payload)

        if command_meta is None and isinstance(text, str):
            command_meta = self._RU_TEXT_TO_COMMAND.get(normalized_text)

        if command_meta is None and isinstance(text, str):
            join_bet = self._extract_join_bet_from_reply_text(normalized_text)
            if join_bet is not None:
                command_meta = ("group_join", None)
                bet = join_bet

        if command_meta is None:
            return self._unsupported(
                envelope=envelope,
                chat_id=self._extract_chat_id(payload) or envelope.source_key,
                chat_type=self._extract_chat_type(payload),
                actor_telegram_id=self._extract_actor_id(payload),
                actor_username=self._extract_actor_username(payload),
                actor_first_name=self._extract_actor_first_name(payload),
            )

        command_type, action = command_meta
        admin_target_username, admin_amount = self._extract_admin_args(text, command_type)
        if admin_amount is not None:
            bet = admin_amount
        return RouterCommand(
            update_id=envelope.update_id,
            chat_id=self._extract_chat_id(payload) or envelope.source_key,
            chat_type=self._extract_chat_type(payload),
            actor_telegram_id=self._extract_actor_id(payload),
            actor_username=self._extract_actor_username(payload),
            actor_first_name=self._extract_actor_first_name(payload),
            command_type=command_type,
            admin_target_username=admin_target_username,
            bet=bet,
            action=action,
            source_key=envelope.source_key,
            raw_payload=payload,
        )

    @staticmethod
    def _resolve_start_game_command(
        payload: dict[str, Any],
        *,
        context: SessionContext | None,
    ) -> tuple[CommandType, str | None]:
        if context is not None and context.reply_action_hint in {"group_open", "group_start", "single_start"}:
            return context.reply_action_hint, None

        message = payload.get("message")
        if isinstance(message, dict):
            chat = message.get("chat")
            if isinstance(chat, dict) and chat.get("type") in {"group", "supergroup"}:
                return "group_open", None

        return "single_start", None

    @staticmethod
    def _resolve_stop_command(payload: dict[str, Any]) -> tuple[CommandType, str | None]:
        message = payload.get("message")
        if isinstance(message, dict):
            chat = message.get("chat")
            if isinstance(chat, dict) and chat.get("type") in {"group", "supergroup"}:
                return "group_stop", None

        return "single_stop", None

    @staticmethod
    def _normalize_command_key(command_key: str) -> str:
        if not command_key.startswith("/"):
            return command_key

        command_without_mention, _, _ = command_key.partition("@")
        return command_without_mention or command_key

    def _from_callback_query(
        self,
        envelope: TelegramUpdateEnvelope,
        payload: dict[str, Any],
    ) -> RouterCommand:
        callback_query = payload.get("callback_query")
        if not isinstance(callback_query, dict):
            return self._unsupported(
                envelope=envelope,
                chat_id=self._extract_chat_id(payload) or envelope.source_key,
                chat_type=self._extract_chat_type(payload),
                actor_telegram_id=self._extract_actor_id(payload),
                actor_username=self._extract_actor_username(payload),
                actor_first_name=self._extract_actor_first_name(payload),
            )

        callback_data = callback_query.get("data")
        command_meta = self._resolve_callback_command(callback_data)
        if command_meta is None:
            return self._unsupported(
                envelope=envelope,
                chat_id=self._extract_chat_id(payload) or envelope.source_key,
                chat_type=self._extract_chat_type(payload),
                actor_telegram_id=self._extract_actor_id(payload),
                actor_username=self._extract_actor_username(payload),
                actor_first_name=self._extract_actor_first_name(payload),
            )

        command_type, action = command_meta
        turn_version = self._extract_turn_version_from_callback(callback_data)
        return RouterCommand(
            update_id=envelope.update_id,
            chat_id=self._extract_chat_id(payload) or envelope.source_key,
            chat_type=self._extract_chat_type(payload),
            actor_telegram_id=self._extract_actor_id(payload),
            actor_username=self._extract_actor_username(payload),
            actor_first_name=self._extract_actor_first_name(payload),
            command_type=command_type,
            action=action,
            turn_version=turn_version,
            source_key=envelope.source_key,
            raw_payload=payload,
        )

    @staticmethod
    def _extract_chat_id(payload: dict[str, Any]) -> str | None:
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

    @staticmethod
    def _extract_actor(payload: dict[str, Any]) -> dict[str, Any] | None:
        message = payload.get("message")
        if isinstance(message, dict):
            actor = message.get("from")
            if isinstance(actor, dict):
                return actor

        callback_query = payload.get("callback_query")
        if isinstance(callback_query, dict):
            actor = callback_query.get("from")
            if isinstance(actor, dict):
                return actor
        return None

    @classmethod
    def _extract_actor_id(cls, payload: dict[str, Any]) -> str | None:
        actor = cls._extract_actor(payload)
        if actor is not None and actor.get("id") is not None:
            return str(actor["id"])
        return None

    @classmethod
    def _extract_actor_username(cls, payload: dict[str, Any]) -> str | None:
        actor = cls._extract_actor(payload)
        if actor is not None:
            username = actor.get("username")
            if isinstance(username, str) and username:
                return username
        return None

    @classmethod
    def _extract_actor_first_name(cls, payload: dict[str, Any]) -> str | None:
        actor = cls._extract_actor(payload)
        if actor is not None:
            first_name = actor.get("first_name")
            if isinstance(first_name, str) and first_name:
                return first_name
        return None

    @staticmethod
    def _extract_chat_type(payload: dict[str, Any]) -> str:
        message = payload.get("message")
        chat_type: str | None = None
        if isinstance(message, dict):
            chat = message.get("chat")
            if isinstance(chat, dict):
                raw = chat.get("type")
                if isinstance(raw, str):
                    chat_type = raw

        if chat_type is None:
            callback_query = payload.get("callback_query")
            if isinstance(callback_query, dict):
                callback_message = callback_query.get("message")
                if isinstance(callback_message, dict):
                    chat = callback_message.get("chat")
                    if isinstance(chat, dict):
                        raw = chat.get("type")
                        if isinstance(raw, str):
                            chat_type = raw

        if chat_type in {"group", "supergroup"}:
            return "group"
        return "single"

    @staticmethod
    def _extract_turn_version_from_callback(callback_data: str | None) -> int | None:
        if not isinstance(callback_data, str):
            return None

        parts = callback_data.split(":")
        for index, part in enumerate(parts):
            if part != "tv":
                continue

            next_index = index + 1
            if next_index >= len(parts):
                continue

            try:
                return int(parts[next_index])
            except ValueError:
                return None
        return None

    @classmethod
    def _resolve_callback_command(
        cls,
        callback_data: str | None,
    ) -> tuple[CommandType, str | None] | None:
        if not isinstance(callback_data, str):
            return None

        if callback_data in cls._CALLBACK_TO_COMMAND:
            return cls._CALLBACK_TO_COMMAND[callback_data]

        parts = callback_data.split(":")
        if len(parts) >= 2 and parts[0] == "action":
            callback_key = ":".join(parts[:2])
            return cls._CALLBACK_TO_COMMAND.get(callback_key)

        return None

    @staticmethod
    def _extract_bet_from_text(text: Any) -> int | None:
        if not isinstance(text, str):
            return None

        parts = text.strip().split()
        if len(parts) < 2:
            return None

        try:
            return int(parts[1])
        except ValueError:
            return None

    @classmethod
    def _extract_join_bet_from_reply_text(cls, text: str) -> int | None:
        match = cls._JOIN_REPLY_PATTERN.match(text)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_admin_args(text: Any, command_type: CommandType) -> tuple[str | None, int | None]:
        if command_type not in {"admin_topup", "admin_ban"}:
            return None, None

        if not isinstance(text, str):
            return None, None

        parts = text.strip().split()
        if len(parts) < 2:
            return None, None

        username = parts[1].lstrip("@") if parts[1] else None

        if command_type == "admin_ban":
            return username or None, None

        if len(parts) < 3:
            return username or None, None

        try:
            amount = int(parts[2])
        except ValueError:
            return username or None, None

        return username or None, amount

    @staticmethod
    def _unsupported(
        *,
        envelope: TelegramUpdateEnvelope,
        chat_id: str,
        chat_type: str,
        actor_telegram_id: str | None,
        actor_username: str | None,
        actor_first_name: str | None,
    ) -> RouterCommand:
        return RouterCommand(
            update_id=envelope.update_id,
            chat_id=chat_id,
            chat_type=chat_type,
            actor_telegram_id=actor_telegram_id,
            actor_username=actor_username,
            actor_first_name=actor_first_name,
            command_type="unsupported",
            source_key=envelope.source_key,
            raw_payload=envelope.payload,
        )
