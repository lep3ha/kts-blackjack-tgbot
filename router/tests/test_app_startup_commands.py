import asyncio
from unittest.mock import AsyncMock

from app.main import RouterApp


class _DummyRedis:
    async def close(self) -> None:
        return None


def test_router_app_start_sets_bot_commands_before_workers() -> None:
    sender = AsyncMock()
    consumer = AsyncMock()
    timer_worker = AsyncMock()
    game_client = AsyncMock()

    app = RouterApp(
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


def test_router_app_bot_commands_include_start_flows() -> None:
    commands = RouterApp._bot_commands()
    command_names = [item["command"] for item in commands]

    assert "start" in command_names
    assert "single_start" in command_names
    assert "group_start" in command_names
    assert "start_round" in command_names
