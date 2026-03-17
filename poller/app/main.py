"""Application factory for the poller service."""
from app.core.config import Settings
from app.core.config import settings
from app.core.resources import AsyncResource
from app.downstream.kafka import KafkaUpdateSink
from app.downstream.sink import UpdateSink
from app.lifecycle import PollerApplication
from app.runtime.runner import PollingRunner
from app.storage.offset_store import FileOffsetStore
from app.storage.offset_store import OffsetStore
from app.telegram.client import RetryPolicy
from app.telegram.client import TelegramPollingClient


def build_polling_runner(
    app_settings: Settings,
    offset_store: OffsetStore | None = None,
    update_sink: UpdateSink | None = None,
) -> PollingRunner:
    """Build the default polling runner for the application."""
    if not app_settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN must be configured")

    client = TelegramPollingClient(
        bot_token=app_settings.telegram_bot_token,
        base_url=app_settings.telegram_base_url,
        poll_timeout=app_settings.telegram_poll_timeout,
        poll_limit=app_settings.telegram_poll_limit,
        request_timeout=app_settings.telegram_request_timeout,
        retry_policy=RetryPolicy(
            base_delay=app_settings.telegram_retry_base_delay,
            max_delay=app_settings.telegram_retry_max_delay,
        ),
    )
    return PollingRunner(
        client=client,
        offset_store=offset_store or FileOffsetStore(app_settings.offset_state_path),
        update_sink=update_sink or KafkaUpdateSink(
            bootstrap_servers=app_settings.kafka_bootstrap_servers,
            topic=app_settings.kafka_topic_updates,
            client_id=app_settings.kafka_client_id,
            required_acks=app_settings.kafka_required_acks,
        ),
        queue_max_size=app_settings.max_in_flight_updates,
        worker_count=app_settings.worker_count,
    )


async def init_app(
    settings_override: Settings | None = None,
    polling_runner: PollingRunner | None = None,
) -> PollerApplication:
    """Initialize the poller application."""
    app_settings = settings_override or settings
    runner = polling_runner or build_polling_runner(app_settings)
    resources: list[AsyncResource] = []
    if isinstance(runner.update_sink, KafkaUpdateSink):
        resources.append(runner.update_sink)
    return PollerApplication(
        settings=app_settings,
        polling_runner=runner,
        resources=resources,
    )
