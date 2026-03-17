import asyncio
from unittest.mock import AsyncMock

from app.main import OrchestratorApp


class _DummyRedis:
    async def close(self) -> None:
        return None


def test_orchestrator_app_start_sets_bot_commands_before_workers() -> None:
    sender = AsyncMock()
    consumer = AsyncMock()
    timer_worker = AsyncMock()
    game_client = AsyncMock()

    app = OrchestratorApp(
        consumer=consumer,
        timer_worker=timer_worker,
        redis=_DummyRedis(),
        game_client=game_client,
        sender_client=sender,
    )

    call_order: list[str] = []

    async def _set_commands(_commands):
        call_order.append("set_my_commands")

    async def _consumer_start():
        call_order.append("consumer_start")

    async def _timer_start():
        call_order.append("timer_start")

    sender.set_my_commands.side_effect = _set_commands
    consumer.start.side_effect = _consumer_start
    timer_worker.start.side_effect = _timer_start

    asyncio.run(app.start())

    assert call_order == ["set_my_commands", "consumer_start", "timer_start"]
    sender.set_my_commands.assert_awaited_once()


def test_orchestrator_app_bot_commands_include_start_flows() -> None:
    commands = OrchestratorApp._bot_commands()
    command_names = [item["command"] for item in commands]

    assert "start" in command_names
    assert "single_start" in command_names
    assert "create_lobby" in command_names
    assert "group_start" in command_names
    assert "join" in command_names
    assert "stop" in command_names


def test_orchestrator_app_bot_commands_describe_arguments_and_group_stop_semantics() -> None:
    commands = {item["command"]: item["description"] for item in OrchestratorApp._bot_commands()}

    assert commands["single_start"] == "Одиночная игра, аргумент: [bet]"
    assert commands["create_lobby"] == "Открыть лобби, аргумент: <bet>"
    assert commands["group_start"] == "Запустить уже открытое лобби"
    assert commands["join"] == "Войти в лобби, аргумент: <bet>"
    assert commands["stop"] == "Single: стоп, group: выйти из раунда"
    assert commands["admin_topup"] == "Пополнить баланс: <username> <amount>"
    assert commands["admin_ban"] == "Забанить игрока: <username>"
