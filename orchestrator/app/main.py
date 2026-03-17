import asyncio
import contextlib
from dataclasses import dataclass
import logging
import signal

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.routing import DeduplicatingCommandProcessor
from app.routing import GameCommandHandlers
from app.routing import HttpGameServiceClient
from app.routing import OrchestratorCommandDispatcher
from app.routing import OrchestratorPipeline
from app.routing import TelegramUpdateNormalizer
from app.sender import TelegramSenderClient
from app.state import RedisDedupStore
from app.state import RedisSessionContextStore
from app.timers import RedisTimerWorker
from app.timers.executor import GameServiceTimeoutExecutor
from app.upstream import KafkaUpdatesConsumer


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OrchestratorApp:
    consumer: KafkaUpdatesConsumer
    timer_worker: RedisTimerWorker
    redis: Redis
    game_client: HttpGameServiceClient
    sender_client: TelegramSenderClient

    async def start(self) -> None:
        await self.sender_client.set_my_commands(self._bot_commands())
        await self.consumer.start()
        await self.timer_worker.start()

    async def stop(self) -> None:
        await self.consumer.stop()
        await self.timer_worker.stop()
        await self.game_client.close()
        await self.sender_client.close()
        await self.redis.close()

    @staticmethod
    def _bot_commands() -> list[dict[str, str]]:
        return [
            {"command": "start", "description": "Показать краткий туториал"},
            {"command": "single_start", "description": "Одиночная игра, аргумент: [bet]"},
            {"command": "create_lobby", "description": "Открыть лобби, аргумент: <bet>"},
            {"command": "group_start", "description": "Запустить уже открытое лобби"},
            {"command": "join", "description": "Войти в лобби, аргумент: <bet>"},
            {"command": "current", "description": "Показать текущее состояние"},
            {"command": "stop", "description": "Single: стоп, group: выйти из раунда"},
            {"command": "admin_topup", "description": "Пополнить баланс: <username> <amount>"},
            {"command": "admin_ban", "description": "Забанить игрока: <username>"},
        ]


def create_app(settings: Settings) -> OrchestratorApp:
    configure_logging(settings.log_level)
    logger.info("Orchestrator application initialized")

    redis = Redis.from_url(settings.redis_url)
    game_client = HttpGameServiceClient(
        base_url=settings.game_service_base_url,
        request_timeout_seconds=settings.game_service_request_timeout_seconds,
    )
    sender_client = TelegramSenderClient(
        base_url=settings.telegram_base_url,
        bot_token=settings.telegram_bot_token,
        request_timeout_seconds=settings.sender_request_timeout_seconds,
    )

    dedup_store = RedisDedupStore(redis)
    session_context_store = RedisSessionContextStore(redis)
    handlers = GameCommandHandlers(
        game_client,
        session_context_store=session_context_store,
        context_ttl_seconds=settings.session_context_ttl_seconds,
    )
    dispatcher = OrchestratorCommandDispatcher()
    dispatcher.register("tutorial", handlers.handle_tutorial)
    dispatcher.register("group_open", handlers.handle_group_open)
    dispatcher.register("group_start", handlers.handle_group_start)
    dispatcher.register("group_join", handlers.handle_group_join)
    dispatcher.register("group_stop", handlers.handle_group_stop)
    dispatcher.register("single_start", handlers.handle_single_start)
    dispatcher.register("single_stop", handlers.handle_single_stop)
    dispatcher.register("player_register", handlers.handle_player_register)
    dispatcher.register("player_action", handlers.handle_player_action)
    dispatcher.register("current_session", handlers.handle_current_session)
    dispatcher.register("admin_topup", handlers.handle_admin_topup)
    dispatcher.register("admin_ban", handlers.handle_admin_ban)

    processor = DeduplicatingCommandProcessor(
        dispatcher=dispatcher,
        dedup_store=dedup_store,
        dedup_ttl_seconds=settings.dedup_ttl_seconds,
    )

    timeout_executor = GameServiceTimeoutExecutor(game_client, sender_client)
    timer_worker = RedisTimerWorker(
        redis_client=redis,
        timeout_executor=timeout_executor,
        retention_seconds=settings.timer_retention_seconds,
        poll_interval_seconds=settings.timer_poll_interval_seconds,
        claim_ttl_seconds=settings.timer_claim_ttl_seconds,
    )

    pipeline = OrchestratorPipeline(
        normalizer=TelegramUpdateNormalizer(),
        processor=processor,
        sender=sender_client,
        timer_scheduler=timer_worker,
        session_context_store=session_context_store,
        context_ttl_seconds=settings.session_context_ttl_seconds,
    )

    consumer = KafkaUpdatesConsumer(settings, envelope_handler=pipeline.process_envelope)
    return OrchestratorApp(
        consumer=consumer,
        timer_worker=timer_worker,
        redis=redis,
        game_client=game_client,
        sender_client=sender_client,
    )


def _install_signal_handlers(shutdown_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _request_shutdown(signal_name: str) -> None:
        logger.info("Shutdown signal received signal=%s", signal_name)
        shutdown_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, _request_shutdown, signum.name)
        except NotImplementedError:
            logger.warning("Signal handlers are not supported for signal=%s", signum.name)


async def run(settings: Settings) -> None:
    app = create_app(settings)
    shutdown_event = asyncio.Event()
    shutdown_task: asyncio.Task[bool] | None = None
    consume_task: asyncio.Task[None] | None = None

    _install_signal_handlers(shutdown_event)
    try:
        await app.start()
        consume_task = asyncio.create_task(app.consumer.consume_forever(), name="kafka-consume-loop")
        shutdown_task = asyncio.create_task(shutdown_event.wait(), name="shutdown-waiter")

        done, pending = await asyncio.wait(
            {consume_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        if consume_task in done:
            await consume_task
            return

        logger.info("Graceful shutdown started")
        consume_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consume_task
    finally:
        if shutdown_task is not None:
            shutdown_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await shutdown_task

        if consume_task is not None:
            consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consume_task

        await app.stop()


def main() -> None:
    settings = get_settings()
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        logger.info("Orchestrator shutdown requested by user")